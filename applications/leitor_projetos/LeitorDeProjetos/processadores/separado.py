"""
Modo "Arquivo único" (lógica original de ler_projeto_separado.py).

Gera UM único arquivo TXT contendo a árvore de pastas e o conteúdo
de cada arquivo de código encontrado.

NOTA DE NOMENCLATURA: no script original este arquivo se chamava
"separado", mas seu comportamento é gerar um único arquivo consolidado
— o oposto do que o nome sugere. A lógica de processamento foi
preservada; o nome/descrição exibidos ao usuário na interface foram
corrigidos para refletir o comportamento real ("Arquivo único").

MUDANÇAS DE COMPORTAMENTO em relação ao script original (autorizadas
explicitamente, não são "reescrita da lógica"):
  1. .env agora é bloqueado por nome de arquivo, sempre — no original
     só era bloqueado se aparecesse como PASTA, então um arquivo
     ".env" na raiz do projeto podia ser lido se sua "extensão" não
     fosse filtrada previamente. Isso era uma falha de segurança
     frente ao que a especificação exige.
  2. print() removido — callback de progresso substitui a saída no
     console, que não faz sentido em uma interface gráfica.
  3. Removidas de IGNORAR_PASTAS as entradas ".gitignore" e
     "pyvenv.cfg" (eram arquivos, não pastas — nunca tinham efeito
     algum, então removê-las não muda comportamento observável).
  4. Removida "src" da lista padrão de pastas ignoradas (ignorar todo
     código-fonte contradiz o propósito da ferramenta; ainda pode ser
     re-adicionada manualmente na tela de Configurações).
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
ErroCallback = Callable[[str, str], None]  # (caminho, motivo)


def listar_arquivos_projeto(
    caminho_projeto: str,
    extensoes: tuple[str, ...],
    pastas_ignoradas: list[str],
    arquivos_ignorados: list[str],
) -> tuple[list[str], list[str], int]:
    """
    Percorre o projeto e classifica arquivos em processáveis e
    ignorados, sem ler o conteúdo (usado para a pré-visualização).

    Retorna: (caminhos_processaveis, caminhos_ignorados, total_sensiveis)
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
    nome_arquivo_saida: str,
    extensoes: tuple[str, ...],
    pastas_ignoradas: list[str],
    arquivos_ignorados: list[str],
    on_progresso: Optional[ProgressoCallback] = None,
    on_erro: Optional[ErroCallback] = None,
    arquivos_processaveis: list[str] | None = None,
    idioma: str = IDIOMA_PADRAO,
) -> ResultadoProcessamento:
    """
    Executa o processamento "arquivo único": percorre o projeto e
    escreve a árvore + conteúdo de cada arquivo processável em um
    único arquivo TXT de saída.

    Deve ser chamado a partir de uma thread separada da UI — esta
    função é bloqueante e não gerencia threading por conta própria.
    """
    processaveis, ignorados_lista, sensiveis = listar_arquivos_projeto(
        caminho_projeto, extensoes, pastas_ignoradas, arquivos_ignorados
    )
    # Uma seleção antiga nunca deve contornar regras de exclusão atuais.
    if arquivos_processaveis is not None:
        selecionados = {os.path.normcase(os.path.abspath(p)) for p in arquivos_processaveis}
        ignorados_lista.extend(p for p in processaveis
                               if os.path.normcase(os.path.abspath(p)) not in selecionados)
        processaveis = [p for p in processaveis if os.path.normcase(os.path.abspath(p)) in selecionados]

    Path(caminho_saida_dir).mkdir(parents=True, exist_ok=True)
    caminho_arquivo_saida = os.path.join(caminho_saida_dir, nome_arquivo_saida)

    total = len(processaveis)
    erros: list[str] = []
    processados_com_sucesso = 0

    with open(caminho_arquivo_saida, "w", encoding="utf-8") as saida:
        saida.write(traduzir("resumo_projeto", idioma, caminho=caminho_projeto))

        for indice, caminho_completo in enumerate(processaveis, start=1):
            nome_exibicao = os.path.relpath(caminho_completo, caminho_projeto)

            if on_progresso:
                on_progresso(ProgressoEvento(
                    arquivo_atual=nome_exibicao,
                    atual=indice,
                    total=total,
                ))

            saida.write(traduzir("arquivo_saida", idioma, nome=nome_exibicao))

            try:
                with open(caminho_completo, "r", encoding="utf-8") as f:
                    conteudo = f.read()
                saida.write(traduzir("conteudo_saida", idioma))
                saida.write(conteudo)
                saida.write("\n\n")
                processados_com_sucesso += 1
            except PermissionError:
                motivo = traduzir("acesso_negado", idioma)
                saida.write(traduzir("aviso_leitura_saida", idioma, motivo=motivo))
                erros.append(f"{nome_exibicao}: {motivo}")
                if on_erro:
                    on_erro(nome_exibicao, motivo)
            except UnicodeDecodeError:
                motivo = traduzir("arquivo_nao_texto", idioma)
                saida.write(traduzir("aviso_leitura_saida", idioma, motivo=motivo))
                erros.append(f"{nome_exibicao}: {motivo}")
                if on_erro:
                    on_erro(nome_exibicao, motivo)
            except OSError as e:
                motivo = str(e)
                saida.write(traduzir("aviso_leitura_saida", idioma, motivo=motivo))
                erros.append(f"{nome_exibicao}: {motivo}")
                if on_erro:
                    on_erro(nome_exibicao, motivo)

    return ResultadoProcessamento(
        encontrados=len(processaveis) + len(ignorados_lista),
        processados=processados_com_sucesso,
        ignorados=len(ignorados_lista),
        sensiveis_ignorados=sensiveis,
        erros=erros,
        caminho_saida=caminho_arquivo_saida,
    )
