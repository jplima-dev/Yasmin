"""
Modo "Arquivos separados" (lógica original de ler_projeto_junto.py).

Para cada arquivo de código encontrado, gera um arquivo .txt
correspondente na pasta de saída, preservando a estrutura de pastas
do projeto original.

NOTA DE NOMENCLATURA: no script original este arquivo se chamava
"junto", mas seu comportamento é gerar MÚLTIPLOS arquivos separados
— o oposto do que o nome sugere. A lógica de processamento foi
preservada; o nome/descrição exibidos ao usuário na interface foram
corrigidos para refletir o comportamento real ("Arquivos separados").

Mesmas mudanças de comportamento autorizadas que em separado.py:
bloqueio real de .env por nome, remoção de print(), sem entradas
mortas em pastas ignoradas. Ver processadores/separado.py para o
detalhamento completo do raciocínio.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from configuracao.idiomas import IDIOMA_PADRAO, traduzir
from utils.arquivos import FiltroIgnorados, eh_arquivo_sensivel


@dataclass
class ResultadoProcessamento:
    encontrados: int
    processados: int
    ignorados: int
    sensiveis_ignorados: int
    erros: list[str]
    caminho_saida: str


@dataclass
class ProgressoEvento:
    arquivo_atual: str
    atual: int
    total: int


ProgressoCallback = Callable[[ProgressoEvento], None]
ErroCallback = Callable[[str, str], None]


def listar_arquivos_projeto(
    caminho_projeto: str,
    extensoes: tuple[str, ...],
    pastas_ignoradas: list[str],
    arquivos_ignorados: list[str],
) -> tuple[list[str], list[str], int]:
    """
    Mesma lógica de classificação usada em separado.py. Duplicada
    aqui deliberadamente (não movida para utils/) porque cada modo
    pode ter conjuntos de extensões diferentes por decisão do
    usuário — manter as funções de processamento de cada modo
    autocontidas evita acoplamento desnecessário entre os dois.
    """
    processaveis: list[str] = []
    ignorados: list[str] = []
    total_sensiveis = 0

    filtro_pastas = FiltroIgnorados(pastas_ignoradas, caminho_projeto)
    filtro_arquivos = FiltroIgnorados(arquivos_ignorados, caminho_projeto)
    extensoes_normalizadas = tuple(e.lower() for e in extensoes)

    for raiz, dirs, arquivos in os.walk(caminho_projeto):
        dirs[:] = [d for d in dirs if not filtro_pastas.corresponde(os.path.join(raiz, d))]

        for nome in sorted(arquivos):
            caminho_completo = os.path.join(raiz, nome)

            if eh_arquivo_sensivel(nome):
                ignorados.append(caminho_completo)
                total_sensiveis += 1
                continue

            if filtro_arquivos.corresponde(caminho_completo):
                ignorados.append(caminho_completo)
                continue

            if nome.lower().endswith(extensoes_normalizadas):
                processaveis.append(caminho_completo)
            else:
                ignorados.append(caminho_completo)

    return processaveis, ignorados, total_sensiveis


def processar(
    caminho_projeto: str,
    caminho_saida_dir: str,
    extensoes: tuple[str, ...],
    pastas_ignoradas: list[str],
    arquivos_ignorados: list[str],
    on_progresso: Optional[ProgressoCallback] = None,
    on_erro: Optional[ErroCallback] = None,
    arquivos_processaveis: list[str] | None = None,
    idioma: str = IDIOMA_PADRAO,
) -> ResultadoProcessamento:
    """
    Executa o processamento "arquivos separados": para cada arquivo
    processável, cria um .txt correspondente na pasta de saída,
    espelhando a estrutura de subpastas do projeto original.

    Deve ser chamado a partir de uma thread separada da UI.
    """
    processaveis, ignorados_lista, sensiveis = listar_arquivos_projeto(
        caminho_projeto, extensoes, pastas_ignoradas, arquivos_ignorados
    )
    if arquivos_processaveis is not None:
        selecionados = {os.path.normcase(os.path.abspath(p)) for p in arquivos_processaveis}
        ignorados_lista.extend(p for p in processaveis
                               if os.path.normcase(os.path.abspath(p)) not in selecionados)
        processaveis = [p for p in processaveis if os.path.normcase(os.path.abspath(p)) in selecionados]

    Path(caminho_saida_dir).mkdir(parents=True, exist_ok=True)

    total = len(processaveis)
    erros: list[str] = []
    processados_com_sucesso = 0

    for indice, caminho_completo in enumerate(processaveis, start=1):
        nome_exibicao = os.path.relpath(caminho_completo, caminho_projeto)

        if on_progresso:
            on_progresso(ProgressoEvento(
                arquivo_atual=nome_exibicao,
                atual=indice,
                total=total,
            ))

        caminho_relativo_dir = os.path.dirname(nome_exibicao)
        pasta_destino = os.path.join(caminho_saida_dir, caminho_relativo_dir)

        try:
            os.makedirs(pasta_destino, exist_ok=True)

            with open(caminho_completo, "r", encoding="utf-8") as f:
                conteudo = f.read()

            nome_arquivo_original = os.path.basename(caminho_completo)
            nome_txt = nome_arquivo_original + ".txt"
            caminho_destino = os.path.join(pasta_destino, nome_txt)

            with open(caminho_destino, "w", encoding="utf-8") as novo_arquivo:
                novo_arquivo.write(traduzir("arquivo_original", idioma, nome=nome_exibicao))
                novo_arquivo.write(traduzir("conteudo_arquivo", idioma))
                novo_arquivo.write(conteudo)

            processados_com_sucesso += 1

        except PermissionError:
            motivo = traduzir("acesso_negado", idioma)
            erros.append(f"{nome_exibicao}: {motivo}")
            if on_erro:
                on_erro(nome_exibicao, motivo)
        except UnicodeDecodeError:
            motivo = traduzir("arquivo_nao_texto", idioma)
            erros.append(f"{nome_exibicao}: {motivo}")
            if on_erro:
                on_erro(nome_exibicao, motivo)
        except OSError as e:
            motivo = str(e)
            erros.append(f"{nome_exibicao}: {motivo}")
            if on_erro:
                on_erro(nome_exibicao, motivo)

    return ResultadoProcessamento(
        encontrados=len(processaveis) + len(ignorados_lista),
        processados=processados_com_sucesso,
        ignorados=len(ignorados_lista),
        sensiveis_ignorados=sensiveis,
        erros=erros,
        caminho_saida=caminho_saida_dir,
    )
