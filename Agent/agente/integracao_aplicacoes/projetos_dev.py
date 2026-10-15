"""Documentação factual de projetos a partir do Analisador de Ink-guginha."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path

from agente.modelos import (Etapa, Observacao, ResultadoFerramenta,
                           ResultadoVerificacao, StatusVerificacao)

from .analisador import analisar_projeto
from .contrato import ContratoAplicacao


def _descricao(raiz: Path) -> tuple[str | None, str | None]:
    """Lê apenas metadados e a introdução de um README existente."""
    manifestos = (("pyproject.toml", "toml"), ("package.json", "json"))
    for nome, formato in manifestos:
        arquivo = raiz / nome
        if not arquivo.is_file() or arquivo.is_symlink() or arquivo.stat().st_size > 128_000:
            continue
        try:
            dados = (tomllib.loads(arquivo.read_text(encoding="utf-8")) if formato == "toml"
                     else json.loads(arquivo.read_text(encoding="utf-8")))
            descricao = dados.get("project", {}).get("description") if formato == "toml" else dados.get("description")
            if isinstance(descricao, str) and descricao.strip():
                return descricao.strip()[:600], nome
        except (OSError, UnicodeError, ValueError, TypeError, AttributeError):
            continue
    for nome in ("README.md", "README.rst", "README.txt"):
        arquivo = raiz / nome
        if not arquivo.is_file() or arquivo.is_symlink():
            continue
        try:
            with arquivo.open(encoding="utf-8") as origem:
                linhas = origem.read(16_384).splitlines()
        except (OSError, UnicodeError):
            continue
        trecho = []
        for linha in linhas:
            linha = linha.strip()
            if not linha or linha.startswith(("#", "!", "<", "[", "```", "---", "===")):
                if trecho:
                    break
                continue
            if linha.startswith(("- ", "* ")):
                if trecho:
                    break
                continue
            trecho.append(linha)
            if sum(map(len, trecho)) >= 600:
                break
        if trecho:
            return " ".join(trecho)[:600], nome
    return None, None


def descrever_projeto(contrato: ContratoAplicacao, caminho: str) -> ResultadoFerramenta:
    analise = analisar_projeto(contrato, caminho)
    if not analise.sucesso:
        return analise
    dados = analise.resultado or {}
    raiz = Path(caminho).expanduser().resolve()
    descricao, fonte = _descricao(raiz)
    resumo = dados.get("resumo") or {}
    linguagens = dados.get("linguagens") or {}
    funcao = (f"Segundo {fonte}, {descricao}" if descricao else
              "Não encontrei descrição do propósito no README ou nos metadados do projeto.")
    mensagem = (f"{raiz.name}: {funcao} A análise encontrou {resumo.get('files', 0)} arquivos "
                f"e {resumo.get('lines', 0)} linhas.")
    return ResultadoFerramenta(True, {
        "operacao": "descrever_projeto", "projeto": str(raiz),
        "fornecedor_analise": contrato.fornecedor, "descricao": descricao,
        "fonte_descricao": fonte, "resumo": resumo, "linguagens": linguagens,
        "mensagem": mensagem,
    })


def escrever_resumo_projeto(contrato: ContratoAplicacao, caminho: str,
                           destino: str, nome: str) -> ResultadoFerramenta:
    if not re.fullmatch(r"[\w.-]+\.md", nome, re.I) or nome.startswith("."):
        return ResultadoFerramenta(False, erro="Nome do Markdown inválido")
    pasta = Path(destino).expanduser().resolve()
    if not pasta.is_dir():
        return ResultadoFerramenta(False, erro=f"Pasta de destino inexistente: {pasta}")
    alvo = pasta / nome
    if alvo.exists():
        return ResultadoFerramenta(False, erro=f"O arquivo já existe; não sobrescrevi: {alvo}")
    resultado = descrever_projeto(contrato, caminho)
    if not resultado.sucesso:
        return resultado
    dados = resultado.resultado or {}
    resumo = dados["resumo"]
    descricao = (dados["descricao"] or "Propósito ainda não documentado no projeto.").replace("<", "&lt;").replace(">", "&gt;")
    fonte = dados["fonte_descricao"] or "inspeção estrutural"
    linguagens = dados["linguagens"]
    linhas = [f"# {Path(caminho).expanduser().resolve().name}", "", "## Sobre", "",
              descricao, "", f"Fonte da descrição: `{fonte}`.", "", "## Estrutura", "",
              f"- Arquivos: {resumo.get('files', 0)}",
              f"- Diretórios: {resumo.get('directories', 0)}",
              f"- Linhas: {resumo.get('lines', 0)}"]
    if linguagens:
        linhas.extend(("", "## Linguagens", ""))
        linhas.extend(f"- {linguagem}" for linguagem in sorted(linguagens))
    conteudo = "\n".join(linhas) + "\n"
    try:
        with alvo.open("x", encoding="utf-8", newline="\n") as arquivo:
            arquivo.write(conteudo)
    except OSError as erro:
        return ResultadoFerramenta(False, erro=f"Não consegui criar {alvo}: {erro}")
    return ResultadoFerramenta(True, {
        "operacao": "escrever_resumo_projeto", "arquivo": str(alvo),
        "sha256": hashlib.sha256(conteudo.encode("utf-8")).hexdigest(),
        "mensagem": f"Criei {alvo}. {dados['mensagem']}",
    })


def verificar_descricao(etapa: Etapa, observacao: Observacao) -> ResultadoVerificacao:
    dados = observacao.dados.get("resultado") or {}
    if not observacao.dados.get("sucesso"):
        return ResultadoVerificacao(StatusVerificacao.FALHA, 1.0,
                                    (observacao.dados.get("erro") or "Leitura falhou",))
    if dados.get("projeto") == str(Path(etapa.parametros["caminho"]).expanduser().resolve()) and isinstance(dados.get("resumo"), dict):
        return ResultadoVerificacao(StatusVerificacao.SUCESSO, 0.9,
                                    (f"Projeto analisado: {dados['projeto']}",))
    return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.2, ("Análise não corresponde ao projeto",))


def verificar_arquivo(etapa: Etapa, observacao: Observacao) -> ResultadoVerificacao:
    dados = observacao.dados.get("resultado") or {}
    if not observacao.dados.get("sucesso"):
        return ResultadoVerificacao(StatusVerificacao.FALHA, 1.0,
                                    (observacao.dados.get("erro") or "Gravação falhou",))
    alvo = Path(etapa.parametros["destino"]).expanduser().resolve() / etapa.parametros["nome"]
    try:
        digest = hashlib.sha256(alvo.read_bytes()).hexdigest()
    except OSError:
        return ResultadoVerificacao(StatusVerificacao.FALHA, 0.95, ("Arquivo não encontrado",))
    if dados.get("arquivo") == str(alvo) and digest == dados.get("sha256"):
        return ResultadoVerificacao(StatusVerificacao.SUCESSO, 0.99,
                                    (f"Arquivo conferido: {alvo}",))
    return ResultadoVerificacao(StatusVerificacao.FALHA, 0.95, ("Conteúdo gravado diverge do resultado",))
