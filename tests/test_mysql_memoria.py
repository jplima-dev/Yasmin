"""Contrato do repositório e migração, sem servidor MySQL no ambiente de CI."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Agent"))

from agente.modelos import Objetivo
from infraestrutura.mysql_memoria import RepositorioMemoriaMySQL


class CursorFalso:
    def __init__(self, banco):
        self.banco = banco
        self.resposta = None
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.banco.consultas.append((sql, params))
        normal = " ".join(sql.split()).upper()
        if normal.startswith("SELECT DIGEST, IMPORTED_COUNT FROM MEMORY_MIGRATIONS"):
            migracao = self.banco.migracoes.get(params[0])
            self.resposta = {"digest": migracao[0], "imported_count": migracao[1]} if migracao else None
        elif normal.startswith("INSERT INTO MEMORY_RECORDS"):
            self.banco.registros[params[0]] = params
        elif normal.startswith("SELECT COUNT(*)"):
            self.resposta = {"total": sum(1 for r in self.banco.registros.values() if r[5] == params[0])}
        elif normal.startswith("DELETE FROM MEMORY_RECORDS WHERE SOURCE_KEY"):
            anterior = len(self.banco.registros)
            self.banco.registros = {chave: registro for chave, registro in self.banco.registros.items()
                                    if not (chave == params[0] and registro[1] == params[1] and registro[5] == params[2])}
            self.rowcount = anterior - len(self.banco.registros)
        elif normal.startswith("DELETE FROM MEMORY_RECORDS"):
            atuais = set(params[1:])
            self.banco.registros = {chave: registro for chave, registro in self.banco.registros.items()
                                    if registro[5] != params[0] or chave in atuais}
        elif normal.startswith("INSERT INTO MEMORY_MIGRATIONS"):
            self.banco.migracoes[params[0]] = (params[1], params[2])
        elif normal.startswith("SELECT ID, CATEGORY"):
            self.resposta = []
        elif normal.startswith("SELECT MEMORY_KEY, CONTENT"):
            self.resposta = [{"memory_key": registro[2], "content": registro[3]}
                             for registro in self.banco.registros.values() if registro[1] == params[0]][:params[1]]

    def fetchone(self):
        return self.resposta

    def fetchall(self):
        return self.resposta or []


class ConexaoFalsa:
    def __init__(self):
        self.consultas = []
        self.registros = {}
        self.migracoes = {}
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return CursorFalso(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


class MySQLMemoriaTests(unittest.TestCase):
    def test_prepara_estrutura_automaticamente(self):
        banco = ConexaoFalsa()
        RepositorioMemoriaMySQL(lambda: banco).preparar()
        sql = " ".join(q for q, _ in banco.consultas).upper()
        self.assertIn("CREATE TABLE IF NOT EXISTS MEMORY_RECORDS", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS MEMORY_MIGRATIONS", sql)
        self.assertIn("INDEX IDX_CATEGORY_EXPIRY", sql)
        self.assertEqual(banco.commits, 1)

    def test_migracao_preserva_json_e_e_idempotente(self):
        banco = ConexaoFalsa()
        repo = RepositorioMemoriaMySQL(lambda: banco)
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "memoria.json"
            original = json.dumps({"usuario": {"nome": "Ruan"},
                                   "preferencias": {"tom": "direto"},
                                   "tarefas": [{"texto": "programar"}]}, ensure_ascii=False)
            caminho.write_text(original, encoding="utf-8")
            self.assertEqual(repo.migrar_json(caminho), 3)
            self.assertEqual(repo.migrar_json(caminho), 0)
            self.assertEqual(caminho.read_text(encoding="utf-8"), original)
            self.assertEqual(len(banco.registros), 3)
            self.assertEqual({r[1] for r in banco.registros.values()}, {"perfil", "preferencia", "tarefa"})

    def test_nova_versao_do_json_sincroniza_remocao_intencional(self):
        banco = ConexaoFalsa()
        repo = RepositorioMemoriaMySQL(lambda: banco)
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "memoria.json"
            caminho.write_text('{"notas": [{"texto": "antiga"}]}', encoding="utf-8")
            self.assertEqual(repo.migrar_json(caminho), 1)
            caminho.write_text('{"notas": []}', encoding="utf-8")
            self.assertEqual(repo.migrar_json(caminho), 0)
            self.assertEqual(len(banco.registros), 0)

    def test_recuperacao_usa_limite_e_parametros(self):
        banco = ConexaoFalsa()
        resultado = RepositorioMemoriaMySQL(lambda: banco).recuperar(
            Objetivo("Prepare meu ambiente de programação"), limite=4)
        self.assertEqual(resultado, [])
        sql, parametros = next((q, p) for q, p in banco.consultas if "SELECT id, category" in q)
        self.assertIn("LIMIT %s", sql)
        self.assertEqual(parametros[-1], 4)
        self.assertTrue(all("%" in termo for termo in parametros[:-1]))

    def test_preferencias_sao_lidas_seletivamente(self):
        banco = ConexaoFalsa()
        repo = RepositorioMemoriaMySQL(lambda: banco)
        repo.salvar("preferencia", "tom", "descontraido", "conversa")
        repo.salvar("fato", "editor", "VS Code", "conversa")
        self.assertEqual(repo.recuperar_preferencias(2), [{"chave": "tom", "valor": "descontraido"}])
        sql, parametros = next((q, p) for q, p in banco.consultas if "SELECT memory_key, content" in q)
        self.assertIn("category=%s", sql)
        self.assertEqual(parametros, ("preferencia", 2))

    def test_esquecimento_remove_somente_registro_da_conversa(self):
        banco = ConexaoFalsa()
        repo = RepositorioMemoriaMySQL(lambda: banco)
        repo.salvar("fato", "editor", "VS Code", "conversa")
        repo.salvar("fato", "editor", "VS Code", "memoria_legada")
        self.assertTrue(repo.esquecer("fato", "editor", "conversa"))
        self.assertFalse(repo.esquecer("fato", "editor", "conversa"))
        self.assertEqual(len(banco.registros), 1)


if __name__ == "__main__":
    unittest.main()
