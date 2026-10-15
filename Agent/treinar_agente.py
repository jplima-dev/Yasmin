"""Treina o classificador local de intenções suportadas pela Yasmin."""

from __future__ import annotations

import argparse
import itertools
import json
import random
from pathlib import Path

from agente.decisao import DecisorInteracao
from agente.modelo_treinavel import ModeloIntencoesLocal, ROTULOS

RAIZ = Path(__file__).resolve().parent
MODELO_PADRAO = RAIZ / "modelos" / "intencoes_local.json"


def exemplos_base() -> list[tuple[str, str]]:
    """Gera 1.000 frases únicas, rotuladas e reproduzíveis."""
    aleatorio = random.Random(20261013)
    prefixos = ("", "yasmin, ", "por favor, ", "aqui no computador, ",
                "antes de trabalhar, ", "para começar hoje, ")
    verbos_preparo = ("preciso preparar", "quero configurar", "me ajude a montar",
                      "deixe pronto", "gostaria de preparar", "organize",
                      "prepare", "configure", "preciso deixar pronto", "ajude a iniciar")
    alvos_preparo = ("meu ambiente de programação", "o ambiente para desenvolver",
                     "uma IDE para programar", "o editor para codar",
                     "meu computador para programar", "o ambiente de desenvolvimento",
                     "uma IDE para trabalhar com Java", "o editor para programar em Java",
                     "o ambiente de programação Java", "meu computador para codar Java")
    finais_preparo = ("", " por favor", " hoje", " para o projeto", " antes da reunião",
                      " aqui", " nesta sessão", " sem perder tempo")
    preparo = [f"{prefixo}{verbo} {alvo}{final}".strip()
               for prefixo, verbo, alvo, final in itertools.product(
                   prefixos, verbos_preparo, alvos_preparo, finais_preparo)]

    verbos_lista = ("liste", "mostre", "quais são", "quero conhecer", "gostaria de ver",
                    "me diga quais são", "veja", "quero listar", "pode mostrar",
                    "quais existem entre")
    alvos_lista = ("os aplicativos disponíveis", "as aplicações da Yasmin",
                   "os módulos do Workspace", "as ferramentas Ink",
                   "os apps instalados", "os aplicativos do ecossistema",
                   "as aplicações Ink-guginha", "os módulos disponíveis",
                   "as ferramentas do Workspace", "os apps da Yasmin")
    finais_lista = ("", " por favor", " agora", " aqui", " neste computador",
                    " para eu escolher", " antes de começar", " que posso abrir")
    lista = [f"{prefixo}{verbo} {alvo}{final}".strip()
             for prefixo, verbo, alvo, final in itertools.product(
                 prefixos, verbos_lista, alvos_lista, finais_lista)]

    pedidos_fora = (
        "abra o navegador", "feche o editor", "apague todos os arquivos",
        "instale um programa novo", "qual é a previsão do tempo",
        "pesquise notícias recentes", "crie uma planilha", "leia meu email",
        "toque uma música", "faça um cálculo", "conte uma curiosidade",
        "quero conversar sobre programação", "explique Java para mim",
        "como preparar o ambiente para programar", "não prepare o ambiente",
        "não liste os aplicativos", "quais aplicativos você recomenda",
        "resuma este arquivo", "abra o projeto no Workspace",
        "execute este comando no terminal", "escreva um teste unitário",
        "corrija o código deste arquivo", "mostre os arquivos do projeto",
        "lembre que eu trabalho com Java", "mude a sua voz",
        "você pode criar um site", "onde fica meu projeto",
        "quero uma IDE mais rápida", "qual editor combina com Java",
        "me ensine a programar", "depure minha aplicação",
        "organize minhas tarefas", "quero ver meus cadernos",
        "faça backup do computador", "exclua o banco de dados",
    )
    finais_fora = ("", " por favor", " agora", " hoje", " aqui",
                   " quando puder", " no meu computador", " para mim",
                   " nesta sessão", " com segurança")
    fora = [f"{prefixo}{pedido}{final}".strip()
            for prefixo, pedido, final in itertools.product(
                ("", "yasmin, ", "por favor, "), pedidos_fora, finais_fora)]

    escolhidos = (
        [(texto, "preparar_programacao") for texto in aleatorio.sample(sorted(set(preparo)), 400)]
        + [(texto, "listar_aplicacoes_ink") for texto in aleatorio.sample(sorted(set(lista)), 300)]
        + [(texto, "nenhuma") for texto in aleatorio.sample(sorted(set(fora)), 300)]
    )
    aleatorio.shuffle(escolhidos)
    if len(escolhidos) != 1000 or len({texto for texto, _ in escolhidos}) != 1000:
        raise RuntimeError("Corpus-base deve ter exatamente 1.000 frases distintas")
    return escolhidos


AVALIACAO = (
    ("Estou precisando de uma IDE para trabalhar em Java", "preparar_programacao"),
    ("Quero deixar o computador pronto para codar", "preparar_programacao"),
    ("Me ajude a montar o ambiente de desenvolvimento", "preparar_programacao"),
    ("Gostaria de configurar meu ambiente para programar Java", "preparar_programacao"),
    ("Preciso de um editor para começar a programar", "preparar_programacao"),
    ("Yasmin, prepare uma IDE para Java", "preparar_programacao"),
    ("Organize o ambiente de programação aqui", "preparar_programacao"),
    ("Deixe tudo pronto para desenvolver", "preparar_programacao"),
    ("Mostre quais módulos existem no Workspace", "listar_aplicacoes_ink"),
    ("Quero ver os aplicativos disponíveis aqui", "listar_aplicacoes_ink"),
    ("Liste as ferramentas da Yasmin", "listar_aplicacoes_ink"),
    ("Quais apps tenho disponíveis", "listar_aplicacoes_ink"),
    ("Me diga quais são as aplicações instaladas", "listar_aplicacoes_ink"),
    ("Gostaria de conhecer os módulos do ecossistema", "listar_aplicacoes_ink"),
    ("Mostre os apps Ink-guginha", "listar_aplicacoes_ink"),
    ("Quero listar os aplicativos que posso abrir", "listar_aplicacoes_ink"),
    ("Apague todos os meus arquivos", "nenhuma"),
    ("Não prepare o ambiente de programação", "nenhuma"),
    ("Não liste as aplicações", "nenhuma"),
    ("Como preparo um ambiente para Java?", "nenhuma"),
    ("Explique o que é uma IDE", "nenhuma"),
    ("Quero conversar sobre código", "nenhuma"),
    ("Abra o Workspace", "nenhuma"),
    ("Leia este arquivo", "nenhuma"),
    ("Instale um editor novo", "nenhuma"),
    ("Mostre os arquivos do projeto", "nenhuma"),
    ("Quais aplicativos você recomenda?", "nenhuma"),
    ("Preciso depurar um bug no meu projeto", "nenhuma"),
    ("Execute um comando no terminal", "nenhuma"),
    ("Quero aprender Java", "nenhuma"),
)


def exemplos_usuario(caminho: Path) -> list[tuple[str, str]]:
    exemplos = []
    with caminho.open(encoding="utf-8") as arquivo:
        for numero, linha in enumerate(arquivo, 1):
            if not linha.strip():
                continue
            try:
                item = json.loads(linha)
                texto, rotulo = item["texto"], item["rotulo"]
            except (ValueError, TypeError, KeyError) as erro:
                raise ValueError(f"Linha {numero} inválida em {caminho}") from erro
            if not isinstance(texto, str) or not texto.strip() or rotulo not in ROTULOS:
                raise ValueError(f"Linha {numero} contém texto ou rótulo inválido")
            exemplos.append((texto, rotulo))
    return exemplos


def avaliar(modelo: ModeloIntencoesLocal) -> tuple[int, list[tuple[str, str, str]]]:
    erros = []
    for texto, esperado in AVALIACAO:
        proposta = modelo.classificar(texto, [], DecisorInteracao._operacoes_semanticas)
        previsto = proposta.get("operacao") if proposta else "nenhuma"
        if previsto != esperado:
            erros.append((texto, esperado, previsto))
    return len(AVALIACAO) - len(erros), erros


def main() -> int:
    parser = argparse.ArgumentParser(description="Treina o modelo local de intenções da Yasmin")
    parser.add_argument("--dados", type=Path, help="JSONL adicional com texto e rotulo")
    parser.add_argument("--saida", type=Path, default=MODELO_PADRAO)
    args = parser.parse_args()
    exemplos = exemplos_base()
    adicionais = exemplos_usuario(args.dados) if args.dados else []
    modelo = ModeloIntencoesLocal()
    modelo.treinar(exemplos + adicionais)
    acertos, erros = avaliar(modelo)
    print(f"Treino: {len(exemplos)} exemplos-base distintos; {len(adicionais)} exemplos adicionais.")
    print(f"Avaliação separada: {acertos}/{len(AVALIACAO)} acertos.")
    for texto, esperado, previsto in erros:
        print(f"  Erro: {texto!r}: esperado={esperado}, previsto={previsto}")
    perigosos = [erro for erro in erros if erro[1] == "nenhuma" and erro[2] != "nenhuma"]
    if acertos / len(AVALIACAO) < 0.85 or perigosos:
        print("Modelo não publicado: avaliação ou segurança insuficiente.")
        return 1
    modelo.salvar(args.saida)
    print(f"Modelo salvo em: {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
