"""Classificador local treinável para intenções suportadas pelo Agent Core."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path


ROTULOS = ("preparar_programacao", "listar_aplicacoes_ink", "nenhuma")
VERSAO = 1


def normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto).casefold())
    base = "".join(letra for letra in base if not unicodedata.combining(letra))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", base)).strip()


def atributos(texto: str) -> Counter[str]:
    palavras = normalizar(texto).split()[:80]
    unidades = [f"u:{palavra}" for palavra in palavras]
    pares = [f"b:{a}_{b}" for a, b in zip(palavras, palavras[1:])]
    return Counter(unidades + pares)


class ModeloIntencoesLocal:
    """Naive Bayes multinomial; só propõe objetivos que o planejador já suporta."""

    def __init__(self) -> None:
        self.documentos: Counter[str] = Counter()
        self.contagens: dict[str, Counter[str]] = {rotulo: Counter() for rotulo in ROTULOS}
        self.totais: Counter[str] = Counter()
        self.vocabulario: set[str] = set()
        self.exemplos = 0

    def treinar(self, exemplos: list[tuple[str, str]]) -> None:
        if not exemplos:
            raise ValueError("Informe exemplos rotulados para treinamento")
        self.__init__()
        for texto, rotulo in exemplos:
            if rotulo not in ROTULOS or not isinstance(texto, str) or not texto.strip():
                raise ValueError(f"Exemplo de treinamento inválido: {rotulo}")
            itens = atributos(texto)
            if not itens:
                raise ValueError("Exemplo sem palavras")
            self.documentos[rotulo] += 1
            self.contagens[rotulo].update(itens)
            self.totais[rotulo] += sum(itens.values())
            self.vocabulario.update(itens)
            self.exemplos += 1

    def probabilidades(self, texto: str) -> dict[str, float]:
        if not self.exemplos:
            return {}
        itens = atributos(texto)
        tamanho = max(len(self.vocabulario), 1)
        logaritmos = {}
        for rotulo in ROTULOS:
            prior = (self.documentos[rotulo] + 1) / (self.exemplos + len(ROTULOS))
            denominador = self.totais[rotulo] + tamanho
            logaritmos[rotulo] = math.log(prior) + sum(
                quantidade * math.log((self.contagens[rotulo][atributo] + 1) / denominador)
                for atributo, quantidade in itens.items())
        maximo = max(logaritmos.values())
        escalados = {rotulo: math.exp(valor - maximo) for rotulo, valor in logaritmos.items()}
        total = sum(escalados.values())
        return {rotulo: valor / total for rotulo, valor in escalados.items()}

    def prever(self, texto: str) -> tuple[str, float]:
        chances = self.probabilidades(texto)
        return max(chances.items(), key=lambda item: item[1]) if chances else ("nenhuma", 0.0)

    def classificar(self, texto: str, historico: list[dict],
                   operacoes: dict[str, dict]) -> dict | None:
        """Abstém-se quando faltar evidência textual ou segurança."""
        frase = normalizar(texto)
        if (not frase or len(frase) > 1000
                or re.search(r"\b(?:nao|nunca|jamais|apague|apagar|exclua|excluir|delete|remova|remover|instale|instalar|desinstale)\b", frase)
                or re.search(r"\b(?:e depois|em seguida|depois disso)\b", frase)
                or frase.startswith(("como ", "por que ", "o que "))):
            return None
        chances = self.probabilidades(frase)
        if not chances:
            return None
        ordem = sorted(chances.items(), key=lambda item: item[1], reverse=True)
        rotulo, confianca = ordem[0]
        if rotulo == "nenhuma" or confianca < 0.92 or confianca - ordem[1][1] < 0.55:
            return None
        if rotulo == "preparar_programacao":
            if ("preparar_programacao" not in operacoes
                    or not re.search(r"\b(?:ambiente|programar|programacao|codar|codigo|desenvolvimento|desenvolver|ide|editor)\b", frase)
                    or not re.search(r"\b(?:preciso|precisando|quero|gostaria|ajude|ajuda|prepare|preparar|pronto|configurar|configure|organize|montar|monte|iniciar|começar|comecar)\b", frase)):
                return None
            return {"operacao": rotulo, "linguagem": "java" if re.search(r"\bjava\b", frase) else "geral"}
        if rotulo == "listar_aplicacoes_ink":
            if ("listar_aplicacoes_ink" not in operacoes
                    or not re.search(r"\b(?:aplicativos|aplicacoes|apps|modulos|ferramentas)\b", frase)
                    or not re.search(r"\b(?:liste|listar|mostre|mostrar|quais|existem|disponiveis|tenho|conhecer|veja)\b", frase)):
                return None
            return {"operacao": rotulo}
        return None

    def salvar(self, caminho: Path) -> None:
        if not self.exemplos:
            raise ValueError("Modelo ainda não treinado")
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        dados = {
            "versao": VERSAO, "rotulos": list(ROTULOS), "exemplos": self.exemplos,
            "documentos": dict(self.documentos), "totais": dict(self.totais),
            "contagens": {rotulo: dict(self.contagens[rotulo]) for rotulo in ROTULOS},
        }
        temporario = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=caminho.parent,
                                             prefix=f".{caminho.name}.", suffix=".tmp",
                                             delete=False) as arquivo:
                temporario = Path(arquivo.name)
                json.dump(dados, arquivo, ensure_ascii=False, separators=(",", ":"))
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, caminho)
        finally:
            if temporario is not None:
                try:
                    temporario.unlink(missing_ok=True)
                except OSError:
                    pass

    @classmethod
    def carregar(cls, caminho: Path) -> "ModeloIntencoesLocal":
        caminho = Path(caminho)
        if caminho.stat().st_size > 2_000_000:
            raise ValueError("Arquivo de modelo excede o limite")
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if (not isinstance(dados, dict) or dados.get("versao") != VERSAO
                or dados.get("rotulos") != list(ROTULOS)):
            raise ValueError("Versão ou rótulos do modelo incompatíveis")
        documentos = dados.get("documentos")
        totais = dados.get("totais")
        contagens = dados.get("contagens")
        exemplos = dados.get("exemplos")
        if (type(exemplos) is not int or exemplos < 1
                or not all(isinstance(parte, dict) and set(parte) == set(ROTULOS)
                           for parte in (documentos, totais, contagens))
                or any(type(valor) is not int or valor < 0
                       for parte in (documentos, totais) for valor in parte.values())
                or any(not isinstance(contagens[rotulo], dict)
                       or any(not isinstance(chave, str) or type(valor) is not int or valor < 0
                              for chave, valor in contagens[rotulo].items())
                       for rotulo in ROTULOS)
                or sum(documentos.values()) != exemplos
                or any(totais[rotulo] != sum(contagens[rotulo].values())
                       for rotulo in ROTULOS)):
            raise ValueError("Arquivo de modelo inválido")
        modelo = cls()
        modelo.exemplos = exemplos
        modelo.documentos = Counter(documentos)
        modelo.totais = Counter(totais)
        modelo.contagens = {rotulo: Counter(contagens[rotulo]) for rotulo in ROTULOS}
        modelo.vocabulario = set().union(*(set(itens) for itens in modelo.contagens.values()))
        return modelo


class MotorDecisaoHibrido:
    """Tenta o modelo local e, se ele se abstiver, usa o motor opcional."""

    def __init__(self, local: ModeloIntencoesLocal | None, externo=None):
        self.local = local
        self.externo = externo

    def propor_plano(self, texto: str, ferramentas: dict[str, dict]) -> dict | None:
        """Planos compostos usam o provedor opcional; o núcleo valida cada etapa."""
        proponente = getattr(self.externo, "propor_plano", None)
        return proponente(texto, ferramentas) if callable(proponente) else None

    def classificar(self, texto: str, historico: list[dict],
                   operacoes: dict[str, dict]) -> dict | None:
        if self.local is not None:
            proposta = self.local.classificar(texto, historico, operacoes)
            if proposta is not None:
                return {**proposta, "_origem": "modelo_local"}
        if self.externo is None:
            return None
        # Mantém a chamada remota somente nos pedidos que já a usavam antes
        # da ampliação do classificador local.
        if not re.search(r"\b(?:preciso|ajude|ajuda|organize|prepar[ae]|deixe|configure|abra|abrir|inicie|fa[cz]a|execute)\b",
                         normalizar(texto)):
            return None
        proposta = self.externo.classificar(texto, historico, operacoes)
        if isinstance(proposta, dict):
            proposta.pop("_origem", None)
        return proposta
