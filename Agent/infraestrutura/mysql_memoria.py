"""Repositório MySQL da memória do agente. O banco `yasm` é criado pelo usuário."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from agente.modelos import Objetivo


def _conexao_padrao():
    try:
        import pymysql
    except ImportError as erro:
        raise RuntimeError("Instale PyMySQL para usar a memória MySQL") from erro
    return pymysql.connect(host=os.environ.get("YASM_MYSQL_HOST", "127.0.0.1"),
                           port=int(os.environ.get("YASM_MYSQL_PORT", "3306")),
                           user=os.environ.get("YASM_MYSQL_USER", "root"),
                           password=os.environ.get("YASM_MYSQL_PASSWORD", ""),
                           database="yasm", charset="utf8mb4", autocommit=False,
                           connect_timeout=3, read_timeout=5, write_timeout=5,
                           cursorclass=pymysql.cursors.DictCursor)


def _chave(*partes) -> str:
    return hashlib.sha256("\0".join(map(str, partes)).encode("utf-8")).hexdigest()


class RepositorioMemoriaMySQL:
    def __init__(self, conectar=None):
        self._conectar = conectar or _conexao_padrao

    def preparar(self) -> None:
        conexao = self._conectar()
        try:
            with conexao.cursor() as cursor:
                cursor.execute("""CREATE TABLE IF NOT EXISTS memory_records (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    source_key CHAR(64) NOT NULL UNIQUE,
                    category VARCHAR(32) NOT NULL,
                    memory_key VARCHAR(191) NOT NULL,
                    content JSON NOT NULL,
                    search_text TEXT NOT NULL,
                    source VARCHAR(255) NOT NULL,
                    importance FLOAT NOT NULL DEFAULT 0.5,
                    confidence FLOAT NOT NULL DEFAULT 1.0,
                    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                    last_used_at DATETIME(6) NULL,
                    expires_at DATETIME(6) NULL,
                    INDEX idx_category_expiry (category, expires_at),
                    INDEX idx_importance (importance)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
                cursor.execute("""CREATE TABLE IF NOT EXISTS memory_migrations (
                    source VARCHAR(255) NOT NULL PRIMARY KEY,
                    digest CHAR(64) NOT NULL,
                    imported_count INT NOT NULL,
                    completed_at DATETIME(6) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
            conexao.commit()
        finally:
            conexao.close()

    def _salvar(self, cursor, categoria: str, chave: str, valor, origem: str,
                importancia: float = 0.5, confianca: float = 1.0, expira_em=None) -> None:
        texto = json.dumps(valor, ensure_ascii=False, default=str)
        cursor.execute("""INSERT INTO memory_records
            (source_key, category, memory_key, content, search_text, source,
             importance, confidence, expires_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE content=VALUES(content), search_text=VALUES(search_text),
              importance=VALUES(importance), confidence=VALUES(confidence),
              expires_at=VALUES(expires_at), updated_at=CURRENT_TIMESTAMP(6)""",
            (_chave(origem, categoria, chave), categoria, str(chave)[:191], texto,
             f"{chave} {texto}", origem[:255], importancia, confianca, expira_em))

    def salvar(self, categoria: str, chave: str, valor, origem: str,
               importancia: float = 0.5, confianca: float = 1.0, expira_em=None) -> None:
        if not 0 <= importancia <= 1 or not 0 <= confianca <= 1:
            raise ValueError("Importância e confiança devem estar entre 0 e 1")
        conexao = self._conectar()
        try:
            with conexao.cursor() as cursor:
                self._salvar(cursor, categoria, chave, valor, origem, importancia, confianca, expira_em)
            conexao.commit()
        except Exception:
            conexao.rollback()
            raise
        finally:
            conexao.close()

    def recuperar(self, objetivo: Objetivo, limite: int = 8) -> list[dict]:
        """Recupera poucas memórias relevantes; não varre o acervo em Python."""
        comuns = {"como", "qual", "quais", "quero", "voce", "você", "sobre", "para",
                  "isso", "aquilo", "aquela", "aquele", "minha", "meu", "seus", "suas",
                  "fazer", "pode", "preciso", "agora", "favor", "conte", "diga"}
        termos = [x for x in re.findall(r"[\wÀ-ÿ]+", objetivo.descricao.lower())
                  if len(x) >= 4 and x not in comuns]
        termos.extend(str(x).lower() for x in objetivo.parametros.values() if isinstance(x, str))
        termos = list(dict.fromkeys(termos))[:8]
        if not termos:
            return []
        condicoes = " OR ".join("search_text LIKE %s" for _ in termos)
        pontuacao = " + ".join("(CASE WHEN search_text LIKE %s THEN 1 ELSE 0 END)" for _ in termos)
        parametros = [f"%{termo.replace('%', '\\%').replace('_', '\\_')}%" for termo in termos]
        conexao = self._conectar()
        try:
            with conexao.cursor() as cursor:
                cursor.execute(f"""SELECT id, category, memory_key, content, importance, confidence,
                    source, created_at, updated_at, last_used_at, expires_at
                    FROM memory_records WHERE (expires_at IS NULL OR expires_at > UTC_TIMESTAMP())
                    AND ({condicoes}) ORDER BY ({pontuacao}) DESC, importance DESC,
                    updated_at DESC LIMIT %s""",
                    (*parametros, *parametros, min(max(limite, 1), 30)))
                registros = cursor.fetchall()
                if registros:
                    ids = [item["id"] for item in registros]
                    marcadores = ",".join(["%s"] * len(ids))
                    cursor.execute(f"UPDATE memory_records SET last_used_at=UTC_TIMESTAMP(6) WHERE id IN ({marcadores})", ids)
            conexao.commit()
            return [{"categoria": item["category"], "chave": item["memory_key"],
                     "valor": json.loads(item["content"]) if isinstance(item["content"], str) else item["content"],
                     "importancia": item["importance"], "confianca": item["confidence"],
                     "origem": item["source"]} for item in registros]
        except Exception:
            conexao.rollback()
            raise
        finally:
            conexao.close()

    def recuperar_preferencias(self, limite: int = 12) -> list[dict]:
        """Lê somente preferências recentes, com limite fixo e sem carregar o acervo."""
        conexao = self._conectar()
        try:
            with conexao.cursor() as cursor:
                cursor.execute("""SELECT memory_key, content FROM memory_records
                    WHERE category=%s AND (expires_at IS NULL OR expires_at > UTC_TIMESTAMP())
                    ORDER BY updated_at DESC LIMIT %s""", ("preferencia", min(max(limite, 1), 30)))
                registros = cursor.fetchall()
            return [{"chave": item["memory_key"],
                     "valor": json.loads(item["content"]) if isinstance(item["content"], str)
                     else item["content"]} for item in registros]
        finally:
            conexao.close()

    def esquecer(self, categoria: str, chave: str, origem: str) -> bool:
        """Remove somente o registro da origem solicitada; não toca no JSON legado."""
        conexao = self._conectar()
        try:
            with conexao.cursor() as cursor:
                cursor.execute("DELETE FROM memory_records WHERE source_key=%s AND category=%s AND source=%s",
                               (_chave(origem, categoria, chave), categoria, origem))
                removidos = cursor.rowcount
            conexao.commit()
            return removidos > 0
        except Exception:
            conexao.rollback()
            raise
        finally:
            conexao.close()

    def registrar_experiencia(self, objetivo: Objetivo, aplicativo: str) -> None:
        if objetivo.parametros.get("tipo") != "preparar_programacao":
            return
        chave = _chave(json.dumps(objetivo.parametros, sort_keys=True), aplicativo)
        self.salvar("experiencia", chave,
                    {"objetivo": objetivo.parametros, "aplicativo": aplicativo, "resultado": "sucesso"},
                    "agente", importancia=0.8, confianca=0.95)

    def registrar_objetivo(self, objetivo: Objetivo, status: str) -> None:
        self.salvar("objetivo", objetivo.id,
                    {"descricao": objetivo.descricao, "tipo": objetivo.tipo,
                     "parametros": objetivo.parametros, "status": status},
                    "agente", importancia=0.6)

    @staticmethod
    def _registros_legados(dados: dict):
        mapas = {"usuario": "perfil", "preferencias": "preferencia", "informacoes": "fato",
                 "notas": "fato", "tarefas": "tarefa", "historico": "historico",
                 "pesquisas": "historico"}
        for secao, categoria in mapas.items():
            valores = dados.get(secao)
            if isinstance(valores, dict):
                for chave, valor in valores.items():
                    yield categoria, f"{secao}.{chave}", valor
            elif isinstance(valores, list):
                for indice, valor in enumerate(valores):
                    yield categoria, f"{secao}.{indice}", valor
        estudo = dados.get("estudo")
        if isinstance(estudo, dict):
            for indice, valor in enumerate(estudo.get("sessoes", [])):
                yield "episodio", f"estudo.sessao.{indice}", valor

    def migrar_json(self, caminho: Path) -> int:
        """Importa uma cópia lógica em transação; jamais modifica o arquivo original."""
        caminho = Path(caminho)
        if not caminho.exists():
            return 0
        bruto = caminho.read_bytes()
        digest = hashlib.sha256(bruto).hexdigest()
        dados = json.loads(bruto.decode("utf-8"))
        if not isinstance(dados, dict):
            raise ValueError(f"Memória legada inválida: {caminho}")
        origem = str(caminho.resolve())
        registros = list(self._registros_legados(dados))
        conexao = self._conectar()
        try:
            with conexao.cursor() as cursor:
                cursor.execute("SELECT digest, imported_count FROM memory_migrations WHERE source=%s", (origem,))
                anterior = cursor.fetchone()
                if anterior and anterior["digest"] == digest:
                    cursor.execute("SELECT COUNT(*) AS total FROM memory_records WHERE source=%s", (origem,))
                    if cursor.fetchone()["total"] == anterior["imported_count"]:
                        return 0
                for categoria, chave, valor in registros:
                    self._salvar(cursor, categoria, chave, valor, origem)
                chaves_atuais = [_chave(origem, categoria, chave) for categoria, chave, _ in registros]
                if chaves_atuais:
                    marcadores = ",".join(["%s"] * len(chaves_atuais))
                    cursor.execute(f"DELETE FROM memory_records WHERE source=%s AND source_key NOT IN ({marcadores})",
                                   (origem, *chaves_atuais))
                else:
                    cursor.execute("DELETE FROM memory_records WHERE source=%s", (origem,))
                cursor.execute("SELECT COUNT(*) AS total FROM memory_records WHERE source=%s", (origem,))
                if cursor.fetchone()["total"] != len(registros):
                    raise RuntimeError("Validação da migração falhou")
                cursor.execute("""INSERT INTO memory_migrations (source, digest, imported_count, completed_at)
                    VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE digest=VALUES(digest),
                    imported_count=VALUES(imported_count), completed_at=VALUES(completed_at)""",
                    (origem, digest, len(registros), datetime.now(timezone.utc).replace(tzinfo=None)))
            conexao.commit()
            return len(registros)
        except Exception:
            conexao.rollback()
            raise
        finally:
            conexao.close()

    def migrar_memorias_existentes(self, pasta: Path) -> int:
        return sum(self.migrar_json(caminho) for caminho in
                   (Path(pasta) / "memoria.json", Path(pasta) / "cerebro" / "memoria.json"))
