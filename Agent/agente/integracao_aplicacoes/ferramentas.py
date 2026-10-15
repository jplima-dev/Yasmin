"""Vincula operações comprovadas ao registro e verificador existentes."""

from __future__ import annotations

from pathlib import Path

from agente.ferramentas import Ferramenta, RegistroFerramentas
from agente.modelos import (Etapa, Observacao, ResultadoFerramenta,
                           ResultadoVerificacao, Risco, StatusVerificacao)
from agente.verificacao import Verificador

from .analisador import analisar_projeto, verificar_analise
from .abertura import abrir_aplicacao, verificar_abertura
from .descoberta import DescobertaAplicacoes, descobrir_aplicacoes
from .estado import observar_aplicacao
from .leitor import (exportar_contexto, listar_arquivos, verificar_arquivos,
                    verificar_exportacao)
from .notebook import listar_cadernos, verificar_cadernos
from .projetos_dev import (descrever_projeto, escrever_resumo_projeto,
                          verificar_arquivo, verificar_descricao)


def registrar_ferramentas_aplicacoes(registro: RegistroFerramentas,
                                    verificador: Verificador,
                                    descoberta: DescobertaAplicacoes,
                                    raiz: Path) -> None:
    raiz = Path(raiz).resolve()
    por_id = {aplicacao.id: aplicacao for aplicacao in descoberta.aplicacoes}

    def listar() -> ResultadoFerramenta:
        atual = descobrir_aplicacoes(raiz)
        return ResultadoFerramenta(True, {
            "operacao": "listar_aplicacoes_ink",
            "mensagem": f"Encontrei {len(atual.aplicacoes)} aplicações Ink-guginha no ecossistema.",
            "aplicacoes": [{"id": app.id, "nome": app.nome, "versao": app.versao,
                            "fornecedor": app.fornecedor, "autor": app.autor,
                            "tipo": app.tipo,
                            "disponivel": app.pasta.is_dir() and (app.entrada is None or app.entrada.is_file()),
                            "operacoes": [op.nome for op in app.operacoes]}
                           for app in atual.aplicacoes],
            "erros": list(atual.erros),
        })

    def estado(aplicacao: str) -> ResultadoFerramenta:
        contrato = por_id.get(aplicacao)
        if contrato is None:
            return ResultadoFerramenta(False, erro=f"Aplicação desconhecida: {aplicacao}")
        return ResultadoFerramenta(True, {
            "operacao": "consultar_estado_aplicacao_ink",
            **observar_aplicacao(contrato).dados,
        })

    registro.registrar(Ferramenta("listar_aplicacoes_ink", "Lista aplicações Ink-guginha disponíveis",
                                 (), Risco.BAIXO, listar, "catalogo_aplicacoes_ink"))
    registro.registrar(Ferramenta("consultar_estado_aplicacao_ink", "Consulta disponibilidade de uma aplicação Ink-guginha",
                                 ("aplicacao",), Risco.BAIXO, estado, "estado_aplicacao_ink"))
    registro.registrar(Ferramenta("abrir_aplicacao_ink", "Abre a interface gráfica de uma aplicação Ink-guginha",
                                 ("aplicacao",), Risco.MEDIO,
                                 lambda aplicacao: abrir_aplicacao(aplicacao, descoberta, raiz),
                                 "abertura_aplicacao_ink"))

    def verificar_catalogo(etapa: Etapa, observacao: Observacao) -> ResultadoVerificacao:
        dados = observacao.dados.get("resultado") or {}
        itens = dados.get("aplicacoes")
        if (not observacao.dados.get("sucesso") or not raiz.is_dir()
                or not isinstance(itens, list)):
            return ResultadoVerificacao(StatusVerificacao.FALHA, 1.0, ("Catálogo não pôde ser lido",))
        ids = [item.get("id") for item in itens if isinstance(item, dict)]
        if len(ids) != len(itens) or len(set(ids)) != len(ids) or dados.get("erros"):
            return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.5,
                                        ("Catálogo incompleto ou com manifestos inválidos",))
        return ResultadoVerificacao(StatusVerificacao.SUCESSO, 0.98,
                                    (f"{len(itens)} aplicações identificadas em {raiz}",))

    def verificar_estado(etapa: Etapa, observacao: Observacao) -> ResultadoVerificacao:
        dados = observacao.dados.get("resultado") or {}
        if not observacao.dados.get("sucesso"):
            return ResultadoVerificacao(StatusVerificacao.FALHA, 1.0,
                                        (observacao.dados.get("erro") or "Consulta falhou",))
        if dados.get("aplicacao") == etapa.parametros.get("aplicacao") and isinstance(dados.get("disponivel"), bool):
            return ResultadoVerificacao(StatusVerificacao.SUCESSO, 0.95,
                                        ("Estado obtido da instalação atual",))
        return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.2, ("Estado sem identificação válida",))

    verificador.registrar("catalogo_aplicacoes_ink", verificar_catalogo)
    verificador.registrar("estado_aplicacao_ink", verificar_estado)
    verificador.registrar("abertura_aplicacao_ink", verificar_abertura)
    verificador.registrar("analise_projeto_ink", verificar_analise)

    analisador = por_id.get("project-analyzer")
    if analisador:
        registro.registrar(Ferramenta("descrever_projeto", "Descreve um projeto a partir de seus metadados e análise factual",
                                     ("caminho",), Risco.BAIXO,
                                     lambda caminho: descrever_projeto(analisador, caminho),
                                     "descricao_projeto"))
        registro.registrar(Ferramenta("escrever_resumo_projeto", "Cria um Markdown factual do projeto sem sobrescrever arquivos",
                                     ("caminho", "destino", "nome"), Risco.MEDIO,
                                     lambda caminho, destino, nome: escrever_resumo_projeto(analisador, caminho, destino, nome),
                                     "arquivo_projeto"))
        verificador.registrar("descricao_projeto", verificar_descricao)
        verificador.registrar("arquivo_projeto", verificar_arquivo)
        for operacao in analisador.operacoes:
            if operacao.nome == "analisar_projeto_ink" and operacao.verificacao == "analise_projeto_ink":
                registro.registrar(Ferramenta(operacao.nome, operacao.descricao,
                                             operacao.parametros, operacao.risco,
                                             lambda caminho: analisar_projeto(analisador, caminho),
                                             operacao.verificacao))

    notebook = por_id.get("notebook")
    if notebook:
        for operacao in notebook.operacoes:
            if operacao.nome == "listar_cadernos_ink" and operacao.verificacao == "cadernos_ink":
                registro.registrar(Ferramenta(operacao.nome, operacao.descricao,
                                             operacao.parametros, operacao.risco,
                                             lambda: listar_cadernos(notebook), operacao.verificacao))
                verificador.registrar("cadernos_ink",
                                     lambda etapa, obs: verificar_cadernos(notebook, etapa, obs))

    leitor = por_id.get("project-reader")
    if leitor:
        for operacao in leitor.operacoes:
            if operacao.nome == "listar_arquivos_projeto_ink" and operacao.verificacao == "arquivos_projeto_ink":
                registro.registrar(Ferramenta(operacao.nome, operacao.descricao,
                                             operacao.parametros, operacao.risco,
                                             lambda caminho: listar_arquivos(leitor, caminho),
                                             operacao.verificacao))
                verificador.registrar("arquivos_projeto_ink",
                                     lambda etapa, obs: verificar_arquivos(leitor, etapa, obs))
            if operacao.nome == "exportar_contexto_projeto_ink" and operacao.verificacao == "contexto_projeto_ink":
                registro.registrar(Ferramenta(operacao.nome, operacao.descricao,
                                             operacao.parametros, operacao.risco,
                                             lambda caminho, destino: exportar_contexto(leitor, caminho, destino),
                                             operacao.verificacao))
                verificador.registrar("contexto_projeto_ink",
                                     lambda etapa, obs: verificar_exportacao(leitor, etapa, obs))
