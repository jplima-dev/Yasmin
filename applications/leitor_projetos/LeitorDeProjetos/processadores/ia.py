"""Planeja e exporta contexto para IA usando apenas a biblioteca padrão.

O plano guarda uma fotografia do conteúdo: prévia e exportação usam os
mesmos textos. Tokens são estimados por ceil(caracteres / 4), não por modelo.
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from configuracao.idiomas import IDIOMA_PADRAO, traduzir
from processadores.separado import ProgressoEvento, ResultadoProcessamento
from utils.arquivos import FiltroIgnorados, eh_arquivo_sensivel

MARCADOR_SAIDA = ".leitor-ia"


def estimar_tokens(texto: str) -> int:
    return (len(texto) + 3) // 4


@dataclass(frozen=True)
class OpcoesIA:
    limite_tokens: int = 30000
    formato: str = "Markdown"
    incluir_arvore: bool = True
    dividir: bool = True

    def __post_init__(self):
        if type(self.limite_tokens) is not int or self.limite_tokens < 100:
            raise ValueError("ia_limite_invalido")
        if self.formato not in ("Markdown", "TXT"):
            raise ValueError("ia_formato_invalido")


@dataclass(frozen=True)
class Bloco:
    caminho: str
    conteudo: str
    trecho: int = 0


@dataclass(frozen=True)
class Parte:
    nome: str
    texto: str
    blocos: tuple[Bloco, ...]

    @property
    def tokens(self) -> int:
        return estimar_tokens(self.texto)


@dataclass(frozen=True)
class PlanoIA:
    nome_projeto: str
    opcoes: OpcoesIA
    partes: tuple[Parte, ...]
    selecionados: int
    caracteres: int
    encontrados: int
    ignorados: int
    sensiveis_ignorados: int
    erros: tuple[str, ...]
    arquivos_divididos: tuple[str, ...]

    @property
    def tokens(self) -> int:
        return sum(parte.tokens for parte in self.partes)


def listar_arquivos_projeto(caminho_projeto, extensoes, pastas_ignoradas, arquivos_ignorados):
    """Aplica os filtros existentes e exclui links e exportações anteriores."""
    processaveis, ignorados = [], []
    sensiveis = 0
    pastas = FiltroIgnorados(pastas_ignoradas, caminho_projeto)
    arquivos = FiltroIgnorados(arquivos_ignorados, caminho_projeto)
    extensoes_normalizadas = tuple(e.lower() for e in extensoes)
    for raiz, dirs, nomes in os.walk(caminho_projeto):
        if (Path(raiz) / MARCADOR_SAIDA).exists():
            dirs[:] = []
            continue
        dirs[:] = sorted(d for d in dirs if not pastas.corresponde(Path(raiz, d))
                         and not Path(raiz, d).is_symlink())
        for nome in sorted(nomes):
            caminho = Path(raiz, nome)
            if eh_arquivo_sensivel(nome):
                sensiveis += 1
                ignorados.append(str(caminho))
            elif arquivos.corresponde(caminho) or caminho.is_symlink() or not nome.lower().endswith(extensoes_normalizadas):
                ignorados.append(str(caminho))
            else:
                processaveis.append(str(caminho))
    return processaveis, ignorados, sensiveis


def _cerca(texto: str) -> str:
    return "`" * max(3, 1 + max((len(m.group()) for m in re.finditer(r"`+", texto)), default=0))


def _arvore(caminhos: list[str]) -> str:
    raiz = {}
    for caminho in caminhos:
        no = raiz
        for componente in caminho.split("/"):
            no = no.setdefault(componente, {})
    linhas = []

    def visitar(no, prefixo=""):
        itens = sorted(no.items())
        for i, (nome, filhos) in enumerate(itens):
            ultimo = i == len(itens) - 1
            linhas.append(prefixo + ("└── " if ultimo else "├── ") + nome)
            visitar(filhos, prefixo + ("    " if ultimo else "│   "))

    visitar(raiz)
    return "\n".join(linhas)


def _renderizar(nome, blocos, opcoes, idioma):
    md = opcoes.formato == "Markdown"
    texto = ("# " if md else "") + traduzir("ia_projeto", idioma, nome=nome) + "\n\n"
    if opcoes.incluir_arvore:
        arvore = _arvore(sorted({b.caminho for b in blocos}))
        texto += ("## " if md else "") + traduzir("ia_arvore_parte", idioma) + "\n\n"
        cerca = _cerca(arvore)
        texto += f"{cerca}text\n{arvore}\n{cerca}\n\n" if md else arvore + "\n\n"
    secoes = [texto]
    for bloco in blocos:
        titulo = bloco.caminho
        if bloco.trecho:
            titulo += " — " + traduzir("ia_trecho", idioma, numero=bloco.trecho)
        secoes.append(("## " if md else "=== ") + titulo + "\n\n")
        if md:
            cerca = _cerca(bloco.conteudo)
            secoes.append(cerca + "\n" + bloco.conteudo
                          + ("" if bloco.conteudo.endswith("\n") else "\n") + cerca + "\n\n")
        else:
            secoes.append(bloco.conteudo + "\n\n")
    return "".join(secoes)


def preparar(caminho_projeto: str, extensoes: tuple[str, ...],
             pastas_ignoradas: list[str], arquivos_ignorados: list[str],
             opcoes: OpcoesIA = OpcoesIA(), arquivos_processaveis=None,
             idioma: str = IDIOMA_PADRAO, on_progresso=None) -> PlanoIA:
    raiz = Path(caminho_projeto).resolve()
    if not raiz.is_dir():
        raise ValueError(traduzir("pasta_projeto_nao_existe", idioma))
    disponiveis, ignorados, sensiveis = listar_arquivos_projeto(
        str(raiz), extensoes, pastas_ignoradas, arquivos_ignorados)
    selecionados = None if arquivos_processaveis is None else {
        os.path.normcase(os.path.abspath(p)) for p in arquivos_processaveis}
    caminhos = [p for p in disponiveis if selecionados is None
                or os.path.normcase(os.path.abspath(p)) in selecionados]
    blocos, erros = [], []
    for i, caminho in enumerate(caminhos, 1):
        relativo = Path(caminho).relative_to(raiz).as_posix()
        if on_progresso:
            on_progresso(ProgressoEvento(relativo, i, len(caminhos)))
        try:
            alvo = Path(caminho).resolve()
            if not alvo.is_relative_to(raiz) or eh_arquivo_sensivel(alvo.name):
                raise OSError(traduzir("ia_arquivo_inseguro", idioma))
            with open(caminho, encoding="utf-8", newline="") as arquivo:
                blocos.append(Bloco(relativo, arquivo.read()))
        except (OSError, UnicodeError) as exc:
            motivo = traduzir("arquivo_nao_texto", idioma) if isinstance(exc, UnicodeError) else str(exc)
            erros.append(f"{relativo}: {motivo}")

    grupos, atual, divididos = [], [], []
    nome = raiz.name or "projeto"

    def cabe(candidatos):
        return estimar_tokens(_renderizar(nome, candidatos, opcoes, idioma)) <= opcoes.limite_tokens

    for bloco in blocos:
        if not opcoes.dividir or cabe(atual + [bloco]):
            atual.append(bloco)
            continue
        if atual:
            grupos.append(atual)
            atual = []
        if cabe([bloco]):
            atual = [bloco]
            continue
        divididos.append(bloco.caminho)
        restante, trecho = bloco.conteudo, 1
        while restante:
            # Busca o maior prefixo que cabe com árvore, título e cercas.
            baixo, alto = 0, min(len(restante), opcoes.limite_tokens * 4)
            while baixo < alto:
                meio = (baixo + alto + 1) // 2
                if cabe([Bloco(bloco.caminho, restante[:meio], trecho)]):
                    baixo = meio
                else:
                    alto = meio - 1
            if baixo == 0:
                raise ValueError(traduzir("ia_limite_metadados", idioma))
            corte = baixo
            if corte < len(restante):
                fim_linha = restante.rfind("\n", 0, corte)
                if fim_linha >= 0:
                    corte = fim_linha + 1
            pedaco = Bloco(bloco.caminho, restante[:corte], trecho)
            restante = restante[corte:]
            trecho += 1
            if restante:
                grupos.append([pedaco])
            else:
                atual = [pedaco]
        if not bloco.conteudo:
            raise ValueError(traduzir("ia_limite_metadados", idioma))
    if atual:
        grupos.append(atual)
    extensao = "md" if opcoes.formato == "Markdown" else "txt"
    partes = tuple(Parte(f"{nome}_parte_{i:02d}.{extensao}",
                         _renderizar(nome, grupo, opcoes, idioma), tuple(grupo))
                   for i, grupo in enumerate(grupos, 1))
    return PlanoIA(nome, opcoes, partes, len(blocos), sum(len(b.conteudo) for b in blocos),
                   len(disponiveis) + len(ignorados),
                   len(ignorados) + len(disponiveis) - len(caminhos), sensiveis,
                   tuple(erros), tuple(divididos))


def exportar(plano: PlanoIA, caminho_saida_dir: str) -> ResultadoProcessamento:
    """Cada execução ganha uma pasta exclusiva; nunca sobrescreve fontes/partes."""
    if not plano.partes:
        raise ValueError("ia_sem_arquivos")
    Path(caminho_saida_dir).mkdir(parents=True, exist_ok=True)
    destino = Path(tempfile.mkdtemp(prefix=f"{plano.nome_projeto}_IA_", dir=caminho_saida_dir))
    try:
        (destino / MARCADOR_SAIDA).write_text("Leitor de Projetos\n", encoding="utf-8")
        for parte in plano.partes:
            with (destino / parte.nome).open("x", encoding="utf-8", newline="") as arquivo:
                arquivo.write(parte.texto)
    except OSError:
        # Limpa somente arquivos desta execução, em diretório recém-criado.
        for parte in plano.partes:
            (destino / parte.nome).unlink(missing_ok=True)
        (destino / MARCADOR_SAIDA).unlink(missing_ok=True)
        destino.rmdir()
        raise
    return ResultadoProcessamento(plano.encontrados, plano.selecionados, plano.ignorados,
                                  plano.sensiveis_ignorados, list(plano.erros), str(destino))
