"""Adapter de consulta do Leitor de Projetos, desenvolvido por Ink-guginha."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from agente.modelos import (Etapa, Observacao, ResultadoFerramenta,
                           ResultadoVerificacao, StatusVerificacao)

from .contrato import ContratoAplicacao


# Executa a função pública no próprio ambiente de importação da aplicação.
# O processo isolado impede que os pacotes genéricos "utils" e "configuracao"
# do aplicativo contaminem os imports do Agent Core.
_CONSULTA = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from configuracao.config import carregar_config
from processadores.ia import listar_arquivos_projeto
from utils.arquivos import eh_arquivo_sensivel
config = carregar_config()
raiz = Path(sys.argv[2]).resolve()
arquivos, ignorados, sensiveis = listar_arquivos_projeto(
    str(raiz), tuple(config['extensoes_separado']),
    config['pastas_ignoradas'], config['arquivos_ignorados'])
amostra = []
for arquivo in arquivos:
    relativo = Path(arquivo).relative_to(raiz)
    if not any(eh_arquivo_sensivel(parte) for parte in relativo.parts):
        amostra.append(relativo.as_posix())
        if len(amostra) == 20:
            break
print(json.dumps({'arquivos': len(arquivos), 'ignorados': len(ignorados),
                  'sensiveis_ignorados': sensiveis, 'amostra': amostra}))
"""


_EXPORTACAO = """
import json, sys
sys.path.insert(0, sys.argv[1])
from configuracao.config import carregar_config
from processadores.ia import OpcoesIA, preparar, exportar
config = carregar_config()
opcoes = OpcoesIA(limite_tokens=config['ia_limite_tokens'],
                  formato='Markdown', incluir_arvore=config['ia_incluir_arvore'],
                  dividir=True)
plano = preparar(sys.argv[2], tuple(config['extensoes_separado']),
                 config['pastas_ignoradas'], config['arquivos_ignorados'], opcoes)
resultado = exportar(plano, sys.argv[3])
print(json.dumps({'destino': resultado.caminho_saida, 'partes': [parte.nome for parte in plano.partes],
                  'selecionados': plano.selecionados, 'erros': list(plano.erros)}))
"""


def _consultar(contrato: ContratoAplicacao, caminho: str) -> dict:
    raiz = Path(caminho).expanduser().resolve()
    if not raiz.is_dir():
        raise ValueError(f"Pasta de projeto inexistente: {raiz}")
    backend = contrato.pasta / "LeitorDeProjetos"
    if not (backend / "processadores" / "ia.py").is_file():
        raise FileNotFoundError("Backend do Leitor de Projetos indisponível")
    processo = subprocess.run(
        [sys.executable, "-I", "-c", _CONSULTA, str(backend), str(raiz)],
        capture_output=True, text=True, encoding="utf-8", timeout=3,
        check=False,
    )
    if processo.returncode:
        raise RuntimeError(f"Consulta do Leitor de Projetos falhou ({processo.returncode})")
    dados = json.loads(processo.stdout)
    if (not isinstance(dados, dict) or
            any(type(dados.get(chave)) is not int or dados[chave] < 0
                for chave in ("arquivos", "ignorados", "sensiveis_ignorados")) or
            not isinstance(dados.get("amostra"), list)):
        raise ValueError("Resposta inválida do Leitor de Projetos")
    return {"projeto": str(raiz), **dados}


def listar_arquivos(contrato: ContratoAplicacao, caminho: str) -> ResultadoFerramenta:
    dados = _consultar(contrato, caminho)
    return ResultadoFerramenta(True, {
        "operacao": "listar_arquivos_projeto_ink",
        "aplicacao": contrato.id,
        "fornecedor": contrato.fornecedor,
        "mensagem": (f"Encontrei {dados['arquivos']} arquivo(s) no projeto {Path(dados['projeto']).name}; "
                     f"{dados['sensiveis_ignorados']} nome(s) sensíveis ignorados."),
        **dados,
    })


def exportar_contexto(contrato: ContratoAplicacao, caminho: str,
                     destino: str) -> ResultadoFerramenta:
    raiz = Path(caminho).expanduser().resolve()
    saida = Path(destino).expanduser().resolve()
    if not raiz.is_dir() or not saida.is_dir():
        return ResultadoFerramenta(False, erro="Projeto ou pasta de destino inexistente")
    backend = contrato.pasta / "LeitorDeProjetos"
    if not (backend / "processadores" / "ia.py").is_file():
        return ResultadoFerramenta(False, erro="Backend do Leitor de Projetos indisponível")
    processo = subprocess.run(
        [sys.executable, "-I", "-c", _EXPORTACAO, str(backend), str(raiz), str(saida)],
        capture_output=True, text=True, encoding="utf-8", timeout=45, check=False,
    )
    if processo.returncode:
        return ResultadoFerramenta(False, erro=f"Exportação do Leitor falhou ({processo.returncode}): {processo.stderr[-400:]}")
    dados = json.loads(processo.stdout)
    if not isinstance(dados, dict) or not isinstance(dados.get("partes"), list):
        return ResultadoFerramenta(False, erro="Resposta inválida da exportação")
    return ResultadoFerramenta(True, {
        "operacao": "exportar_contexto_projeto_ink", "aplicacao": contrato.id,
        "fornecedor": contrato.fornecedor, "projeto": str(raiz), **dados,
        "mensagem": f"O Leitor preparou {len(dados['partes'])} arquivo(s) de contexto em {dados['destino']}.",
    })


def verificar_exportacao(contrato: ContratoAplicacao, etapa: Etapa,
                        observacao: Observacao) -> ResultadoVerificacao:
    if not observacao.dados.get("sucesso"):
        return ResultadoVerificacao(StatusVerificacao.FALHA, 1.0,
                                    (observacao.dados.get("erro") or "Exportação falhou",))
    dados = observacao.dados.get("resultado") or {}
    raiz = Path(etapa.parametros["destino"]).expanduser().resolve()
    saida = Path(dados.get("destino", "")).resolve()
    partes = dados.get("partes")
    if (dados.get("aplicacao") != contrato.id or not saida.is_dir()
            or not saida.is_relative_to(raiz) or not isinstance(partes, list)
            or not partes or len(partes) != len(set(partes))):
        return ResultadoVerificacao(StatusVerificacao.FALHA, 0.95,
                                    ("Diretório de exportação ou lista de arquivos inválida",))
    if all((saida / nome).is_file() and (saida / nome).stat().st_size > 0
           for nome in partes if Path(nome).name == nome) and all(Path(nome).name == nome for nome in partes):
        return ResultadoVerificacao(StatusVerificacao.SUCESSO, 0.98,
                                    (f"Arquivos exportados e conferidos em {saida}",))
    return ResultadoVerificacao(StatusVerificacao.FALHA, 0.95,
                                ("Arquivo exportado ausente ou vazio",))


def verificar_arquivos(contrato: ContratoAplicacao, etapa: Etapa,
                       observacao: Observacao) -> ResultadoVerificacao:
    if not observacao.dados.get("sucesso"):
        return ResultadoVerificacao(StatusVerificacao.FALHA, 1.0,
                                    (observacao.dados.get("erro") or "Consulta falhou",))
    anterior = observacao.dados.get("resultado") or {}
    try:
        atual = _consultar(contrato, etapa.parametros["caminho"])
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as erro:
        return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.2,
                                    (f"Não foi possível confirmar a listagem: {type(erro).__name__}",))
    campos = ("projeto", "arquivos", "ignorados", "sensiveis_ignorados", "amostra")
    if anterior.get("aplicacao") == contrato.id and all(anterior.get(c) == atual[c] for c in campos):
        return ResultadoVerificacao(StatusVerificacao.SUCESSO, 0.95,
                                    (f"Projeto existe: {atual['projeto']}",
                                     f"Arquivos classificados: {atual['arquivos']}",))
    return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.4,
                                ("Arquivos ou filtros mudaram durante a verificação",))
