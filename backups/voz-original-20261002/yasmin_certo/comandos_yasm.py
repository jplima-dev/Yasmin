import ast
import math
import random
import re
import threading
import unicodedata
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, quote, quote_plus, urlparse

try:
    import requests
except ImportError:
    requests = None
try:
    import yt_dlp
except ImportError:
    yt_dlp = None
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from config_yasm import SITES, TIMEOUT_INTERNET, MAX_RESULTADOS_PESQUISA
from memoria_yasm import memoria, salvar_memoria, registrar_historico
from util_yasm import normalizar, extrair_depois, remover_palavras_iniciais, remover_chamada
import voz_yasm as voz
import audio_yasm as audio
import apps_yas
import falas

informar = voz.falar



def alterar_nome(texto):
    """Altera o nome salvo quando o usuario pedir explicitamente."""
    nome = extrair_depois(
        texto,
        (
            "me chame de",
            "pode me chamar de",
            "meu nome e",
            "meu nome é",
        ),
    )
    nome = nome.strip(" .,!?")
    if not nome:
        return None
    if len(nome.split()) > 4:
        return None
    memoria["usuario"]["nome"] = nome.title()
    salvar_memoria(memoria)
    return falas.escolher("nome_alterado", nome=memoria["usuario"]["nome"])


def nome_usuario():
    return memoria.get("usuario", {}).get("nome", "amigo")

timers_ativos = []

TOPICOS_PYTHON = {
    "variaveis": {
        "aliases": ("variavel", "variaveis"),
        "resumo": "Variaveis guardam valores para voce reutilizar depois. Em Python, voce nao declara tipo; o valor define o tipo naquele momento.",
        "exemplo": "nome = 'Juan'; idade = 18; print(nome, idade)",
        "treino": "Crie tres variaveis: seu nome, sua idade e uma linguagem que voce quer aprender. Depois imprima tudo.",
    },
    "listas": {
        "aliases": ("lista", "listas", "array", "vetor"),
        "resumo": "Listas guardam varios valores em ordem. Elas podem crescer, mudar e ser percorridas com for.",
        "exemplo": "numeros = [1, 2, 3]; numeros.append(4); print(numeros)",
        "treino": "Crie uma lista com cinco tecnologias e mostre cada uma usando um for.",
    },
    "dicionarios": {
        "aliases": ("dicionario", "dicionarios", "dict", "dictionary"),
        "resumo": "Dicionarios guardam pares de chave e valor. Sao otimos para representar objetos simples.",
        "exemplo": "aluno = {'nome': 'Juan', 'curso': 'Python'}; print(aluno['nome'])",
        "treino": "Crie um dicionario com nome, idade e objetivo de estudo. Depois leia cada campo.",
    },
    "condicionais": {
        "aliases": ("if", "else", "elif", "condicional", "condicionais"),
        "resumo": "Condicionais deixam o programa escolher caminhos usando if, elif e else.",
        "exemplo": "if idade >= 18: print('maior de idade') else: print('menor de idade')",
        "treino": "Peca uma nota e diga se ela foi aprovado, recuperacao ou reprovado.",
    },
    "loops": {
        "aliases": ("loop", "loops", "for", "while", "laco", "lacos", "repeticao"),
        "resumo": "Loops repetem uma acao. Use for quando souber a sequencia, e while quando depender de uma condicao.",
        "exemplo": "for numero in range(5): print(numero)",
        "treino": "Mostre os numeros de 1 a 10 e depois calcule a soma deles.",
    },
    "funcoes": {
        "aliases": ("funcao", "funcoes", "def", "parametro", "return"),
        "resumo": "Funcoes agrupam uma acao com nome, entradas e, se precisar, um retorno.",
        "exemplo": "def dobrar(numero): return numero * 2",
        "treino": "Crie uma funcao que receba um nome e retorne uma saudacao.",
    },
    "classes": {
        "aliases": ("classe", "classes", "objeto", "objetos", "poo", "orientacao a objetos"),
        "resumo": "Classes sao moldes para criar objetos com dados e comportamentos.",
        "exemplo": "class Pessoa: pass; pessoa = Pessoa()",
        "treino": "Crie uma classe Livro com titulo e autor, depois instancie dois livros.",
    },
    "arquivos": {
        "aliases": ("arquivo", "arquivos", "ler arquivo", "salvar arquivo", "open"),
        "resumo": "Python consegue ler e escrever arquivos usando open. Use with para fechar o arquivo automaticamente.",
        "exemplo": "with open('dados.txt', 'w', encoding='utf-8') as arquivo: arquivo.write('oi')",
        "treino": "Crie um arquivo chamado notas.txt e salve tres linhas nele.",
    },
    "excecoes": {
        "aliases": ("excecao", "excecoes", "try", "except", "erro", "erros"),
        "resumo": "Excecoes tratam falhas sem derrubar o programa. Use try e except para reagir a problemas esperados.",
        "exemplo": "try: numero = int(texto) except ValueError: print('numero invalido')",
        "treino": "Peca um numero ao usuario e trate o caso de ele digitar texto.",
    },
    "comprehensions": {
        "aliases": ("comprehension", "comprehensions", "list comprehension"),
        "resumo": "Comprehensions criam listas, conjuntos ou dicionarios de forma curta e expressiva.",
        "exemplo": "quadrados = [n * n for n in range(10)]",
        "treino": "Crie uma lista com os quadrados dos numeros de 1 a 20.",
    },
}

EXERCICIOS_PYTHON = [
    {
        "nivel": "iniciante",
        "topico": "variaveis",
        "pergunta": "Crie variaveis para nome, idade e cidade. Depois imprima uma frase usando esses valores.",
        "solucao": "nome = 'Juan'\nidade = 18\ncidade = 'Sao Paulo'\nprint(f'Meu nome e {nome}, tenho {idade} anos e moro em {cidade}.')",
    },
    {
        "nivel": "iniciante",
        "topico": "listas",
        "pergunta": "Crie uma lista com cinco numeros e mostre apenas os numeros pares.",
        "solucao": "numeros = [1, 2, 3, 4, 5]\nfor numero in numeros:\n    if numero % 2 == 0:\n        print(numero)",
    },
    {
        "nivel": "iniciante",
        "topico": "funcoes",
        "pergunta": "Crie uma funcao chamada saudacao que receba um nome e retorne uma mensagem de boas-vindas.",
        "solucao": "def saudacao(nome):\n    return f'Bem-vindo, {nome}!'\n\nprint(saudacao('Juan'))",
    },
    {
        "nivel": "intermediario",
        "topico": "dicionarios",
        "pergunta": "Crie uma lista de alunos, cada aluno sendo um dicionario com nome e nota. Mostre quem tirou nota maior ou igual a sete.",
        "solucao": "alunos = [{'nome': 'Ana', 'nota': 8}, {'nome': 'Bia', 'nota': 6}]\nfor aluno in alunos:\n    if aluno['nota'] >= 7:\n        print(aluno['nome'])",
    },
    {
        "nivel": "intermediario",
        "topico": "arquivos",
        "pergunta": "Salve uma lista de tarefas em um arquivo texto, uma tarefa por linha.",
        "solucao": "tarefas = ['estudar Python', 'praticar loops', 'revisar funcoes']\nwith open('tarefas.txt', 'w', encoding='utf-8') as arquivo:\n    for tarefa in tarefas:\n        arquivo.write(tarefa + '\\n')",
    },
]

QUIZ_PYTHON = [
    {
        "pergunta": "Qual comando cria uma funcao em Python: def, function ou func?",
        "respostas": ("def",),
        "explicacao": "Em Python, funcoes sao criadas com def.",
    },
    {
        "pergunta": "Qual tipo combina chave e valor: lista, dicionario ou tupla?",
        "respostas": ("dicionario", "dict"),
        "explicacao": "Dicionarios guardam dados em pares de chave e valor.",
    },
    {
        "pergunta": "Qual loop costuma ser melhor para percorrer uma lista: for ou while?",
        "respostas": ("for",),
        "explicacao": "For e a escolha natural quando voce ja tem uma sequencia para percorrer.",
    },
    {
        "pergunta": "Qual bloco trata erros em Python: try except ou if else?",
        "respostas": ("try", "except", "try except"),
        "explicacao": "Try e except sao usados para tratar excecoes.",
    },
]

def abrir_url(nome, url):
    webbrowser.open(url)
    return f"Abrindo {nome}."


def internet_pronta():
    return requests is not None and BeautifulSoup is not None


def limpar_link_duckduckgo(link):
    if not link:
        return ""

    if link.startswith("//"):
        link = "https:" + link

    if "duckduckgo.com/l/" in link or link.startswith("/l/"):
        partes = urlparse(link)
        parametros = parse_qs(partes.query)
        destino = parametros.get("uddg", [""])[0]
        # parse_qs ja decodifica o redirecionamento; decodificar de novo
        # altera URLs que contêm escapes pertencentes ao destino.
        return destino if destino else link

    return link


def buscar_web(consulta, limite=MAX_RESULTADOS_PESQUISA):
    """
    Pesquisa no DuckDuckGo.

    Mantém vários resultados internamente para que a Yasm
    possa abrir qualquer resultado depois.

    A fala da Yasm não depende desta função diretamente.
    """

    if not internet_pronta():
        return []

    resposta = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": consulta},
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=TIMEOUT_INTERNET,
    )

    resposta.raise_for_status()

    pagina = BeautifulSoup(
        resposta.text,
        "html.parser"
    )

    resultados = []

    for item in pagina.select(".result"):

        titulo = item.select_one(
            ".result__a"
        )

        resumo = item.select_one(
            ".result__snippet"
        )

        if not titulo:
            continue

        texto_titulo = titulo.get_text(
            " ",
            strip=True
        )

        link = limpar_link_duckduckgo(
            titulo.get(
                "href",
                ""
            )
        )

        texto_resumo = (
            resumo.get_text(
                " ",
                strip=True
            )
            if resumo
            else ""
        )

        if texto_titulo and link:

            resultados.append(
                {
                    "titulo": texto_titulo,
                    "link": link,
                    "resumo": texto_resumo,
                }
            )

        if len(resultados) >= limite:
            break

    return resultados


def guardar_pesquisa(consulta, resultados):
    memoria.setdefault("pesquisas", []).append(
        {
            "consulta": consulta,
            "resultados": resultados,
            "criado_em": datetime.now().isoformat(timespec="seconds"),
        }
    )
    memoria["pesquisas"] = memoria["pesquisas"][-10:]
    salvar_memoria(memoria)


def formatar_resultados_pesquisa(consulta, resultados):
    """
    Mostra somente os títulos dos resultados mais relevantes.

    Os resultados completos continuam salvos na memória.
    """

    if not resultados:
        return falas.escolher(
            "pesquisa_sem_resultado",
            consulta=consulta
        )

    quantidade = min(
        2,
        len(resultados)
    )

    partes = [
        f"Encontrei {quantidade} resultados sobre {consulta}."
    ]

    for indice, resultado in enumerate(
        resultados[:2],
        start=1
    ):

        titulo = str(
            resultado.get(
                "titulo",
                ""
            )
        ).strip()

        if not titulo:
            titulo = f"resultado {indice}"

        partes.append(
            f"Resultado {indice}: {titulo}."
        )

    if len(resultados) >= 2:

        partes.append(
            "Posso abrir o primeiro ou o segundo resultado."
        )

    else:

        partes.append(
            "Posso abrir esse resultado para você."
        )

    return " ".join(
        partes
    )

def pesquisar_google(consulta):

    if not consulta:
        return falas.escolher(
            "pesquisa_vazia"
        )

    if not internet_pronta():

        url = (
            "https://www.google.com/search?q="
            + quote_plus(consulta)
        )

        webbrowser.open(
            url
        )

        return (
            "Não consegui consultar os resultados agora, "
            "então abri a pesquisa no navegador."
        )

    try:

        resultados = buscar_web(
            consulta
        )

        if not resultados:

            return falas.escolher(
                "pesquisa_sem_resultado",
                consulta=consulta
            )

        # Mantém todos os resultados salvos.
        guardar_pesquisa(
            consulta,
            resultados
        )

        # Fala somente os dois títulos principais.
        return formatar_resultados_pesquisa(
            consulta,
            resultados
        )

    except Exception as erro:

        print(
            "[Erro na pesquisa] "
            f"{type(erro).__name__}: {erro!r}"
        )

        url = (
            "https://www.google.com/search?q="
            + quote_plus(consulta)
        )

        webbrowser.open(
            url
        )

        return (
            f"Tive dificuldade para processar "
            f"a pesquisa por {consulta}, "
            "então abri os resultados no navegador."
        )

def abrir_resultado_pesquisa(texto):
    """
    Abre um resultado da última pesquisa.

    Aceita várias formas naturais, por exemplo:

        abre o segundo resultado
        abrir o segundo
        abra resultado dois
        pode abrir o primeiro resultado
        abre esse link
        abra essa pagina
        abre a primeira
        pode abrir o segundo para mim
    """

    texto_normalizado = normalizar(
        texto
    ).strip()

    if not texto_normalizado:
        return None

    # ========================================================
    # 1. VERIFICA SE A FALA PARECE UM PEDIDO DE ABERTURA
    # ========================================================

    verbos_abertura = (
        "abrir",
        "abre",
        "abra",
        "abrir",
        "abrindo",
        "pode abrir",
        "mostra",
        "mostre",
        "acessa",
        "acesse",
    )

    palavras_objeto = (
        "resultado",
        "resultados",
        "link",
        "pagina",
        "fonte",
    )

    # Pelo menos uma forma de abertura
    tem_verbo = any(
        texto_normalizado.startswith(verbo)
        or f" {verbo} " in f" {texto_normalizado} "
        for verbo in verbos_abertura
    )

    tem_objeto = any(
        palavra in texto_normalizado
        for palavra in palavras_objeto
    )

    # Também aceitamos:
    # "abre o primeiro"
    # "abra o segundo"
    # sem a palavra "resultado".
    ordinais = (
        "primeiro",
        "primeira",
        "segundo",
        "segunda",
        "terceiro",
        "terceira",
        "quarto",
        "quarta",
        "quinto",
        "quinta",
        "um",
        "dois",
        "tres",
        "três",
        "quatro",
        "cinco",
        "1",
        "2",
        "3",
        "4",
        "5",
    )

    tem_numero = any(
        palavra in texto_normalizado.split()
        for palavra in ordinais
    )

    # ========================================================
    # "abre esse link", "abre essa pagina", etc.
    # ========================================================

    frases_diretas = (
        "abre esse link",
        "abra esse link",
        "abrir esse link",

        "abre o link",
        "abra o link",
        "abrir o link",

        "abre essa pagina",
        "abra essa pagina",
        "abrir essa pagina",

        "abre a pagina",
        "abra a pagina",
        "abrir a pagina",

        "abre essa fonte",
        "abra essa fonte",
        "abrir essa fonte",

        "abre a fonte",
        "abra a fonte",
        "abrir a fonte",
    )

    eh_frase_direta = any(
        frase in texto_normalizado
        for frase in frases_diretas
    )

    # Se não parece um comando de abertura, sai.
    if not (
        eh_frase_direta
        or (tem_verbo and tem_numero)
        or (tem_verbo and tem_objeto)
    ):
        return None

    # ========================================================
    # 2. VERIFICA SE EXISTE UMA PESQUISA
    # ========================================================

    pesquisas = memoria.get(
        "pesquisas",
        []
    )

    if not pesquisas:
        return falas.escolher(
            "resultado_inexistente"
        )

    resultados = pesquisas[-1].get(
        "resultados",
        []
    )

    if not resultados:
        return falas.escolher(
            "resultado_inexistente"
        )

    # ========================================================
    # 3. IDENTIFICA O RESULTADO
    # ========================================================

    numeros = {
        "um": 1,
        "primeiro": 1,
        "primeira": 1,
        "1": 1,

        "dois": 2,
        "segundo": 2,
        "segunda": 2,
        "2": 2,

        "tres": 3,
        "três": 3,
        "terceiro": 3,
        "terceira": 3,
        "3": 3,

        "quatro": 4,
        "quarto": 4,
        "quarta": 4,
        "4": 4,

        "cinco": 5,
        "quinto": 5,
        "quinta": 5,
        "5": 5,
    }

    indice = 1

    palavras = texto_normalizado.split()

    # Primeiro procura correspondência exata por palavra.
    for palavra in palavras:

        if palavra in numeros:

            indice = numeros[
                palavra
            ]

            break

    # ========================================================
    # 4. SE NÃO DISSE O NÚMERO
    #
    # "abre esse link"
    # "abre essa página"
    #
    # Abre o primeiro resultado.
    # ========================================================

    # indice continua 1.

    # ========================================================
    # 5. VERIFICA SE EXISTE
    # ========================================================

    if indice > len(resultados):

        return falas.escolher(
            "resultado_numero_invalido"
        )

    resultado = resultados[
        indice - 1
    ]

    link = resultado.get(
        "link"
    )

    titulo = resultado.get(
        "titulo",
        f"resultado {indice}"
    )

    if not link:

        return falas.escolher(
            "resultado_numero_invalido"
        )

    # ========================================================
    # 6. ABRE NO NAVEGADOR
    # ========================================================

    try:

        webbrowser.open_new_tab(
            link
        )

    except Exception:

        webbrowser.open(
            link
        )

    # ========================================================
    # 7. RESPOSTA
    # ========================================================

    return falas.escolher(
        "resultado_aberto",
        indice=indice,
        titulo=titulo,
    )


def resumir_wikipedia(termo):

    if requests is None:
        return None

    try:

        url = (
            "https://pt.wikipedia.org/api/rest_v1/page/summary/"
            + quote(termo)
        )

        resposta = requests.get(
            url,
            headers={
                "User-Agent": "YasmAssistant/1.0"
            },
            timeout=TIMEOUT_INTERNET,
        )

        if resposta.status_code != 200:
            return None

        dados = resposta.json()

        resumo = dados.get(
            "extract",
            ""
        )

        if not resumo:
            return None

        resumo = " ".join(
            resumo.split()
        ).strip()

        # ----------------------------------------------------
        # Mantém a resposta confortável para voz.
        # ----------------------------------------------------

        if len(resumo) > 320:

            resumo = (
                resumo[:320]
                .rsplit(" ", 1)[0]
                + "..."
            )

        return resumo

    except Exception as erro:

        print(
            "[Erro na Wikipedia] "
            f"{type(erro).__name__}: {erro!r}"
        )

        return None


def responder_pergunta_internet(texto):

    texto_normalizado = normalizar(
        texto
    )

    # ========================================================
    # NÃO INTERFERIR COM A IDENTIDADE DA YASM
    # ========================================================

    if (
        texto_normalizado.startswith(
            "quem e voce"
        )
        or texto_normalizado.startswith(
            "qual e seu nome"
        )
    ):
        return None

    # ========================================================
    # GATILHOS DE PERGUNTA
    # ========================================================

    gatilhos = (
        "o que e",
        "o que sao",
        "quem e",
        "quem foi",
        "quem ganhou",
        "qual foi",
        "qual e",
        "quando foi",
        "onde fica",
        "onde foi",
        "por que",
        "porque",
        "como funciona",
        "me explique",
        "me explica",
        "resuma",
    )

    termo = ""

    for gatilho in gatilhos:

        if texto_normalizado.startswith(
            gatilho + " "
        ):

            termo = (
                texto_normalizado
                .split(
                    gatilho,
                    1
                )[1]
                .strip()
            )

            break

    if not termo:
        return None

    # ========================================================
    # PYTHON
    # ========================================================

    if "python" in termo:

        resposta_python = explicar_python(
            texto_normalizado
        )

        if resposta_python:
            return resposta_python

    # ========================================================
    # WIKIPÉDIA
    # ========================================================

    resumo = resumir_wikipedia(
        termo
    )

    if resumo:

        return resumo

    # ========================================================
    # PESQUISA WEB
    # ========================================================

    return pesquisar_google(
        termo
    )


def tocar_musica(texto):
    consulta = extrair_depois(
        texto,
        (
            "poe a musica",
            "poe musica",
            "poe uma musica",
            "coloca a musica",
            "coloca musica",
            "coloca uma musica",
            "toque a musica",
            "toque musica",
            "toque uma musica",
            "tocar a musica",
            "tocar musica",
            "tocar uma musica",
            "coloque a musica",
            "colocar a musica",
            "coloque musica",
            "colocar musica",
            "coloque uma musica",
            "colocar uma musica",
            "poe",
            "toque",
            "tocar",
        ),
    )
    consulta = remover_palavras_iniciais(consulta, {"uma", "um", "a", "o", "musica"})

    if not consulta and memoria.get("preferencias", {}).get("ultima_musica"):
        if "de novo" in normalizar(texto) or "ultima" in normalizar(texto):
            consulta = memoria["preferencias"]["ultima_musica"]

    if not consulta:
        memoria.setdefault("preferencias", {})["musica_pendente"] = True
        salvar_memoria(memoria)
        return "Qual musica voce quer que eu toque?"

    memoria["preferencias"]["ultima_musica"] = consulta
    memoria["preferencias"]["musica_pendente"] = False
    salvar_memoria(memoria)

    video = encontrar_video_youtube(consulta)

    if video:
        webbrowser.open(video["url"])
        return falas.escolher("musica_tocando", titulo=video["titulo"])

    url = "https://www.youtube.com/results?search_query=" + quote_plus(consulta)
    webbrowser.open(url)
    return falas.escolher("musica_busca", consulta=consulta)


def encontrar_video_youtube(consulta):
    if yt_dlp is None:
        return None

    try:
        opcoes = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(f"ytsearch1:{consulta}", download=False)

        entradas = info.get("entries") or []
        if not entradas:
            return None

        video = entradas[0]
        video_id = video.get("id")
        titulo = video.get("title") or consulta
        url = video.get("url") or ""

        if video_id:
            url = "https://www.youtube.com/watch?v=" + video_id
        elif url and not url.startswith("http"):
            url = "https://www.youtube.com/watch?v=" + url

        if not url:
            return None

        return {"titulo": titulo, "url": url}
    except Exception as erro:
        print(f"[Erro musica] {type(erro).__name__}: {erro!r}")
        return None


def musica_pendente():
    return bool(
        memoria
        .get("preferencias", {})
        .get("musica_pendente", False)
    )


def responder_musica_pendente(texto):
    if not musica_pendente():
        return None

    consulta = remover_chamada(texto) or normalizar(texto)
    consulta = consulta.strip()

    if not consulta:
        return "Pode me dizer o nome da musica?"

    return tocar_musica("toque " + consulta)


def lembrar_informacao(texto):
    conteudo = extrair_depois(
        texto,
        (
            "lembre que",
            "lembra que",
            "anote que",
            "salve que",
            "guarde que",
            "memorize que",
        ),
    )

    if not conteudo:
        return None

    memoria.setdefault("notas", []).append(
        {
            "texto": conteudo,
            "criado_em": datetime.now().isoformat(timespec="seconds"),
        }
    )
    salvar_memoria(memoria)
    return falas.escolher("memoria_guardada")


def listar_memoria():
    notas = memoria.get("notas", [])

    if not notas:
        return falas.escolher("memoria_vazia")

    ultimas_notas = [nota["texto"] for nota in notas[-5:]]
    return falas.escolher("notas_listadas", notas="; ".join(ultimas_notas))


def apagar_notas():
    memoria["notas"] = []
    salvar_memoria(memoria)
    return falas.escolher("notas_apagadas")


def criar_tarefa(texto):
    tarefa = extrair_depois(
        texto,
        (
            "adicione tarefa",
            "crie tarefa",
            "nova tarefa",
            "anote tarefa",
            "lembre me de",
            "lembre-me de",
        ),
    )

    if not tarefa:
        return None

    memoria.setdefault("tarefas", []).append(
        {
            "texto": tarefa,
            "concluida": False,
            "criado_em": datetime.now().isoformat(timespec="seconds"),
        }
    )
    salvar_memoria(memoria)
    return falas.escolher("tarefa_adicionada", tarefa=tarefa)


def listar_tarefas():
    tarefas = [
        tarefa["texto"]
        for tarefa in memoria.get("tarefas", [])
        if not tarefa.get("concluida")
    ]

    if not tarefas:
        return falas.escolher("tarefas_vazias")

    return "Suas tarefas pendentes sao: " + "; ".join(tarefas[:6]) + "."


def concluir_tarefa(texto):
    alvo = extrair_depois(
        texto,
        (
            "concluir tarefa",
            "marcar tarefa",
            "terminei",
            "conclui",
        ),
    )
    tarefas = memoria.get("tarefas", [])
    pendentes = [tarefa for tarefa in tarefas if not tarefa.get("concluida")]

    if not pendentes:
        return falas.escolher("tarefas_vazias")

    tarefa_escolhida = None

    if alvo:
        for tarefa in pendentes:
            if alvo in normalizar(tarefa["texto"]):
                tarefa_escolhida = tarefa
                break

    if tarefa_escolhida is None:
        if alvo:
            return f"Nao encontrei uma tarefa pendente com o nome {alvo}."
        tarefa_escolhida = pendentes[0]

    tarefa_escolhida["concluida"] = True
    tarefa_escolhida["concluida_em"] = datetime.now().isoformat(timespec="seconds")
    salvar_memoria(memoria)
    return falas.escolher("tarefa_concluida", tarefa=tarefa_escolhida["texto"])


def identificar_topico_python(texto):
    texto_normalizado = normalizar(texto)

    for nome, dados in TOPICOS_PYTHON.items():
        for alias in dados["aliases"]:
            if re.search(r"(?<!\w)" + re.escape(normalizar(alias)) + r"(?!\w)", texto_normalizado):
                return nome

    return None


def registrar_topico_estudado(topico):
    estudo = memoria.setdefault("estudo", {})
    topicos = estudo.setdefault("topicos_vistos", [])

    if topico and topico not in topicos:
        topicos.append(topico)
        salvar_memoria(memoria)


def explicar_python(texto):
    texto_normalizado = normalizar(texto)
    gatilhos = (
        "explique",
        "me explique",
        "me ensine",
        "ensine",
        "como funciona",
        "o que e",
        "o que sao",
    )

    if "python" not in texto_normalizado and not identificar_topico_python(texto_normalizado):
        return None

    if not any(gatilho in texto_normalizado for gatilho in gatilhos):
        return None

    topico = identificar_topico_python(texto_normalizado)

    if not topico:
        return (
            "Python e uma linguagem clara e muito usada para automacao, dados, web e inteligencia artificial. "
            "Para estudar bem, comece por variaveis, listas, condicionais, loops e funcoes."
        )

    dados = TOPICOS_PYTHON[topico]
    registrar_topico_estudado(topico)
    return f"{dados['resumo']} Exemplo: {dados['exemplo']}. Treino: {dados['treino']}"


def abrir_documentacao_python(texto):
    texto_normalizado = normalizar(texto)

    if (
        "documentacao" not in texto_normalizado
        and "docs" not in texto_normalizado
        and "manual do python" not in texto_normalizado
    ):
        return None

    topico = identificar_topico_python(texto_normalizado)

    if topico:
        url = "https://docs.python.org/pt-br/3/search.html?q=" + quote_plus(topico)
        webbrowser.open(url)
        return f"Abrindo a documentacao do Python sobre {topico}."

    webbrowser.open(SITES["documentacao python"])
    return "Abrindo a documentacao oficial do Python em portugues."


def criar_exercicio_python(texto):
    texto_normalizado = normalizar(texto)

    if (
        "exercicio" not in texto_normalizado
        and "treino de python" not in texto_normalizado
        and "praticar python" not in texto_normalizado
        and "me desafie" not in texto_normalizado
    ):
        return None

    topico = identificar_topico_python(texto_normalizado)
    candidatos = EXERCICIOS_PYTHON

    if topico:
        candidatos_topico = [ex for ex in EXERCICIOS_PYTHON if ex["topico"] == topico]
        if candidatos_topico:
            candidatos = candidatos_topico

    exercicio = random.choice(candidatos)
    estudo = memoria.setdefault("estudo", {})
    estudo["exercicio_atual"] = exercicio
    estudo.setdefault("exercicios", []).append(
        {
            "topico": exercicio["topico"],
            "pergunta": exercicio["pergunta"],
            "criado_em": datetime.now().isoformat(timespec="seconds"),
        }
    )
    salvar_memoria(memoria)

    return f"Desafio de {exercicio['topico']}: {exercicio['pergunta']} Quando quiser, diga: Yasm, mostrar solucao."


def mostrar_solucao_exercicio(texto):
    texto_normalizado = normalizar(texto)

    if (
        "mostrar solucao" not in texto_normalizado
        and "mostre a solucao" not in texto_normalizado
        and "qual a resposta" not in texto_normalizado
        and "ver resposta" not in texto_normalizado
    ):
        return None

    exercicio = memoria.get("estudo", {}).get("exercicio_atual")

    if not exercicio:
        return falas.escolher("solucao_inexistente")

    return falas.escolher("solucao", solucao=exercicio["solucao"])


def iniciar_quiz_python(texto):
    texto_normalizado = normalizar(texto)

    if "quiz" not in texto_normalizado and "pergunta de python" not in texto_normalizado:
        return None

    pergunta = random.choice(QUIZ_PYTHON)
    indice = QUIZ_PYTHON.index(pergunta)
    memoria["estudo"]["quiz_atual"] = indice
    salvar_memoria(memoria)
    return pergunta["pergunta"]


def responder_quiz_python(texto):
    quiz_atual = memoria.get("estudo", {}).get("quiz_atual")

    if quiz_atual is None:
        return None

    if type(quiz_atual) is not int or not 0 <= quiz_atual < len(QUIZ_PYTHON):
        memoria["estudo"]["quiz_atual"] = None
        return None

    texto_normalizado = normalizar(texto)
    resposta_curta = len(texto_normalizado.split()) <= 6

    if not resposta_curta and not any(gatilho in texto_normalizado for gatilho in ("resposta", "acho que", "alternativa")):
        return None

    pergunta = QUIZ_PYTHON[quiz_atual]
    acertou = any(
        re.search(r"(?<!\w)" + re.escape(normalizar(resposta)) + r"(?!\w)", texto_normalizado)
        for resposta in pergunta["respostas"]
    )
    memoria["estudo"]["quiz_atual"] = None

    if acertou:
        memoria["estudo"]["pontuacao_quiz"] = memoria["estudo"].get("pontuacao_quiz", 0) + 1
        salvar_memoria(memoria)
        return falas.escolher("quiz_acerto", explicacao=pergunta["explicacao"])

    salvar_memoria(memoria)
    return falas.escolher("quiz_erro", explicacao=pergunta["explicacao"])


def plano_estudo_python(texto):
    texto_normalizado = normalizar(texto)

    if "plano de estudo" not in texto_normalizado and "modo estudo" not in texto_normalizado and "estudar python" not in texto_normalizado:
        return None

    return (
        "Plano de estudo Python: primeiro variaveis e tipos; depois listas e dicionarios; "
        "depois condicionais e loops; em seguida funcoes; depois arquivos, excecoes e projetos pequenos. "
        "Hoje eu sugiro vinte minutos de teoria, trinta de exercicios e dez de revisao."
    )


def registrar_sessao_estudo(texto):
    texto_normalizado = normalizar(texto)

    if "estudei" not in texto_normalizado and "aprendi" not in texto_normalizado and "revisao concluida" not in texto_normalizado:
        return None

    conteudo = extrair_depois(texto_normalizado, ("estudei", "aprendi", "revisao concluida"))
    conteudo = conteudo or "Python"
    topico = identificar_topico_python(conteudo) or conteudo

    memoria["estudo"].setdefault("sessoes", []).append(
        {
            "topico": topico,
            "criado_em": datetime.now().isoformat(timespec="seconds"),
        }
    )
    registrar_topico_estudado(topico)
    salvar_memoria(memoria)
    return falas.escolher("sessao_estudo", topico=topico)


def progresso_estudo(texto):
    texto_normalizado = normalizar(texto)

    if "progresso" not in texto_normalizado and "meu estudo" not in texto_normalizado and "o que eu estudei" not in texto_normalizado:
        return None

    estudo = memoria.get("estudo", {})
    topicos = estudo.get("topicos_vistos", [])
    exercicios = len(estudo.get("exercicios", []))
    pontos = estudo.get("pontuacao_quiz", 0)

    if not topicos and exercicios == 0 and pontos == 0:
        return falas.escolher("progresso_vazio")

    topicos_texto = ", ".join(topicos[-5:]) if topicos else "nenhum topico registrado"
    return f"Seu progresso: topicos vistos: {topicos_texto}. Exercicios gerados: {exercicios}. Pontos no quiz: {pontos}."


def consultar_clima(texto):
    texto_normalizado = normalizar(texto)

    if "clima" not in texto_normalizado and "temperatura" not in texto_normalizado:
        return None

    cidade = extrair_depois(texto_normalizado, ("clima em", "temperatura em", "tempo em"))
    if not cidade:
        cidade = memoria.get("preferencias", {}).get("cidade", "")

    if not cidade:
        return falas.escolher("clima_cidade")

    if requests is None:
        return "Para consultar clima, instale as dependencias com pip install -r requirements.txt."

    try:
        url = "https://wttr.in/" + quote(cidade) + "?format=j1&lang=pt"
        resposta = requests.get(url, timeout=TIMEOUT_INTERNET, headers={"User-Agent": "YasmAssistant/1.0"})
        resposta.raise_for_status()
        dados = resposta.json()
        atual = dados["current_condition"][0]
        temperatura = atual["temp_C"]
        sensacao = atual["FeelsLikeC"]
        descricao = atual["weatherDesc"][0]["value"]

        memoria["preferencias"]["cidade"] = cidade
        salvar_memoria(memoria)
        return falas.escolher("clima", cidade=cidade, temperatura=temperatura, sensacao=sensacao, descricao=descricao)
    except Exception as erro:
        print(f"[Erro clima] {type(erro).__name__}: {erro!r}")
        return f"Nao consegui consultar o clima de {cidade} agora."


def iniciar_timer(texto):
    texto_normalizado = normalizar(texto)

    if "pomodoro" not in texto_normalizado and "timer" not in texto_normalizado and "temporizador" not in texto_normalizado:
        return None

    minutos = 25 if "pomodoro" in texto_normalizado else 5
    encontrado = re.search(r"(\d+)", texto_normalizado)

    if encontrado:
        minutos = int(encontrado.group(1))

    minutos = max(1, min(minutos, 180))

    def avisar_timer():
        informar(f"Timer de {minutos} minutos concluido.")

    timer = threading.Timer(minutos * 60, avisar_timer)
    timer.daemon = True
    timer.start()
    timers_ativos.append(timer)

    return falas.escolher("timer", minutos=minutos)


def calcular_expressao_segura(expressao):
    if len(expressao) > 500:
        raise ValueError("expressao muito longa")

    operadores = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b,
        ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a ** b,
        ast.USub: lambda a: -a,
        ast.UAdd: lambda a: +a,
    }

    def avaliar(no):
        if isinstance(no, ast.Expression):
            return avaliar(no.body)

        if isinstance(no, ast.Constant) and type(no.value) in (int, float):
            return verificar_limites(no.value)

        if isinstance(no, ast.BinOp) and type(no.op) in operadores:
            esquerda, direita = avaliar(no.left), avaliar(no.right)
            if isinstance(no.op, ast.Pow) and abs(direita) > 1000:
                raise ValueError("expoente muito grande")
            return verificar_limites(operadores[type(no.op)](esquerda, direita))

        if isinstance(no, ast.UnaryOp) and type(no.op) in operadores:
            return verificar_limites(operadores[type(no.op)](avaliar(no.operand)))

        raise ValueError("expressao invalida")

    def verificar_limites(valor):
        if type(valor) is int:
            if valor.bit_length() > 4096:
                raise ValueError("resultado muito grande")
        elif type(valor) is not float or not math.isfinite(valor):
            raise ValueError("resultado invalido")
        return valor

    arvore = ast.parse(expressao, mode="eval")
    if sum(1 for _ in ast.walk(arvore)) > 100:
        raise ValueError("expressao muito complexa")
    return avaliar(arvore)


def calcular_comando(texto):
    texto_normalizado = normalizar(texto)

    if "calcule" not in texto_normalizado and "quanto e" not in texto_normalizado and "calcular" not in texto_normalizado:
        return None

    # A normalizacao usada pelos demais comandos remove os operadores e
    # separadores decimais. Preserve-os ao extrair uma expressao matematica.
    texto_calculo = unicodedata.normalize("NFD", str(texto or "").lower())
    texto_calculo = "".join(c for c in texto_calculo if unicodedata.category(c) != "Mn")
    gatilho = re.search(r"\b(?:calcule|calcular|quanto\s+e)\b", texto_calculo)
    if not gatilho:
        return None
    expressao = texto_calculo[gatilho.end():].strip().rstrip("?!")
    expressao = (
        expressao.replace("mais", "+")
        .replace("menos", "-")
        .replace("vezes", "*")
        .replace("x", "*")
        .replace("dividido por", "/")
        .replace("dividido", "/")
        .replace("elevado a", "**")
        .replace(",", ".")
    )
    expressao = expressao.strip()

    if not expressao.strip():
        return falas.escolher("calculo_vazio")

    if re.search(r"[^0-9+\-*/().%\s]", expressao):
        return falas.escolher("calculo_erro")

    try:
        resultado = calcular_expressao_segura(expressao)
        return falas.escolher("calculo_resultado", resultado=resultado)
    except Exception:
        return falas.escolher("calculo_erro")


def relatorio_sistema():
    notas = len(memoria.get("notas", []))
    tarefas = len([t for t in memoria.get("tarefas", []) if not t.get("concluida")])
    pesquisas = len(memoria.get("pesquisas", []))
    exercicios = len(memoria.get("estudo", {}).get("exercicios", []))
    return (
        "Sistema pronto em modo offline primeiro. Entrada de audio: sounddevice. "
        f"Reconhecimento: {audio.motor_reconhecimento()}. "
        f"{audio.diagnostico_audio()}. "
        f"Tenho {notas} notas, {tarefas} tarefas pendentes, "
        f"{pesquisas} pesquisas recentes e {exercicios} exercicios de Python gerados."
    )


def comandos_disponiveis():
    return (
        "Voce pode pedir hora, data, status, ajuda, lembrar notas, listar memoria, "
        "criar tarefas, listar tarefas, pesquisar na internet, abrir resultados, consultar clima, "
        "tocar uma musica, abrir documentacao do Python, pedir explicacoes, exercicios, quiz, "
        "plano de estudo, timer pomodoro e calculos simples. Tudo isso funciona localmente; "
        "a internet so e usada quando voce pede pesquisa, musica, clima, site ou documentacao."
    )


def abrir_site_comando(texto):
    texto_normalizado = normalizar(texto)

    for nome, url in SITES.items():
        if f"abrir {nome}" in texto_normalizado or f"abra {nome}" in texto_normalizado:
            return abrir_url(nome, url)

    return None


def pesquisar_comando(texto):

    consulta = extrair_depois(
        texto,
        (
            "pesquise na internet sobre",
            "pesquisar na internet sobre",
            "procure na internet por",
            "procure na internet sobre",
            "busque na internet por",
            "busque na internet sobre",
            "pesquise sobre",
            "pesquise por",
            "pesquisar por",
            "procure por",
            "buscar por",
            "busque por",
            "pesquisar",
            "pesquise",
        ),
    )

    if not consulta:
        return None

    consulta = consulta.strip()

    if not consulta:
        return falas.escolher(
            "pesquisa_vazia"
        )

    # --------------------------------------------------------
    # Pesquisa local/web do comandos_yasm.
    # --------------------------------------------------------

    resposta = pesquisar_google(
        consulta
    )

    if resposta:
        return resposta

    return falas.escolher(
        "pesquisa_falhou"
    )


def calibrar_audio_comando(texto):
    texto_normalizado = normalizar(texto)

    if "calibrar microfone" not in texto_normalizado and "recalibrar" not in texto_normalizado:
        return None

    informar("Tudo bem. Fique em silencio por dois segundos.")
    audio.calibrar_sounddevice()
    return falas.escolher("microfone_recalibrado")



def responder(texto):
    texto_original = str(texto or "").strip()
    texto = remover_chamada(texto_original) or normalizar(texto_original)

    if not texto:
        return falas.escolher("chamada", nome=nome_usuario())

    if eh_encerramento(texto):
        return "encerrar"

    # O conteudo de uma nota ou tarefa pode conter outros comandos.
    for prefixos, executar in (
        (("lembre que", "lembra que", "anote que", "guarde que", "salve que", "memorize que"), lembrar_informacao),
        (("adicione tarefa", "crie tarefa", "nova tarefa", "anote tarefa", "lembre me de"), criar_tarefa),
        (("concluir tarefa", "marcar tarefa", "terminei", "conclui"), concluir_tarefa),
    ):
        if any(texto == prefixo or texto.startswith(prefixo + " ") for prefixo in prefixos):
            resposta = executar(texto)
            return resposta or "Diga o conteudo que voce quer registrar."

    resposta_calculo = calcular_comando(texto_original)
    if resposta_calculo:
        return resposta_calculo

    # Caminho ultra-rapido para comandos simples e frequentes.
    if "que horas" in texto or "hora agora" in texto or "horario" in texto or texto in {"hora", "horas", "qual a hora", "qual e a hora"}:
        return falas.escolher("hora", hora=datetime.now().strftime("%H:%M"))
    if "que dia" in texto or "qual a data" in texto or "qual e a data" in texto or texto in {"data", "qual o dia de hoje"}:
        return falas.escolher("data", data=datetime.now().strftime("%d/%m/%Y"))
    if texto in {"obrigado", "obrigada", "valeu", "valeu yasm", "valeu yasmin", "vlw"}:
        return falas.escolher("agradecimento")
    if texto in {"oi", "ola", "e ai", "eai", "opa", "bom dia", "boa tarde", "boa noite"}:
        return falas.escolher("chamada", nome=nome_usuario())
    if texto in {"como voce esta", "tudo bem", "voce esta bem"}:
        return falas.escolher("como_estou")

    resposta_musica_pendente = responder_musica_pendente(texto)
    if resposta_musica_pendente:
        return resposta_musica_pendente

    if any(
        g in texto
        for g in (
            "toque",
            "tocar",
            "coloque musica",
            "coloque a musica",
            "coloque uma musica",
            "coloca musica",
            "coloca a musica",
            "poe musica",
            "poe uma musica",
            "poe a musica",
        )
    ):
        return tocar_musica(texto)

    # Aplicativos locais: fechamento direto e prioritario.
    # Isso evita depender de outras regras do dispatcher.
    texto_app = normalizar(texto)
    verbos_fechar = (
        "fechar ",
        "fecha ",
        "feche ",
        "encerra ",
        "encerrar ",
        "pare ",
        "parar ",
    )

    if texto_app.startswith(verbos_fechar):
        aplicativo = apps_yas.identificar_aplicativo(texto_app)
        if aplicativo:
            return apps_yas.fechar_aplicativo(aplicativo)

    # Mantem o detector completo como segunda camada.
    resposta_app = apps_yas.comando_fechar_aplicativo(texto)
    if resposta_app:
        return resposta_app

    # Abrir aplicativo pelo nome ou por uma frase curta.
    resposta_app = apps_yas.comando_abrir_aplicativo(texto)
    if resposta_app:
        return resposta_app

    # Comandos locais primeiro: sao instantaneos e nao gastam API.
    for func in (
        responder_quiz_python, alterar_nome, iniciar_timer, calcular_comando,
        abrir_documentacao_python, plano_estudo_python, explicar_python,
        criar_exercicio_python, mostrar_solucao_exercicio, iniciar_quiz_python,
        registrar_sessao_estudo, progresso_estudo, lembrar_informacao, criar_tarefa,
        abrir_site_comando, abrir_resultado_pesquisa, pesquisar_comando, consultar_clima,
        calibrar_audio_comando,
    ):
        resultado = func(texto)
        if resultado:
            return resultado

    if "status" in texto or "relatorio" in texto or "diagnostico" in texto or "sistema" in texto:
        return relatorio_sistema()
    if "apagar notas" in texto or "limpar memoria" in texto or "apague minhas notas" in texto:
        return apagar_notas()
    if "minhas tarefas" in texto or "listar tarefas" in texto or "tarefas pendentes" in texto:
        return listar_tarefas()
    if any(x in texto for x in ("concluir tarefa", "marcar tarefa", "terminei", "conclui")):
        return concluir_tarefa(texto)
    if any(x in texto for x in ("o que voce sabe", "minhas notas", "o que voce lembra")):
        return listar_memoria()
    if any(x in texto for x in ("ajuda", "o que voce faz", "voce consegue", "comandos")):
        return comandos_disponiveis()
    if "seu nome" in texto or texto in {"quem e voce", "o que e voce", "o que voce e", "como voce se chama"}:
        return falas.escolher("identidade")
    if "meu nome" in texto or "quem sou eu" in texto:
        return falas.escolher("nome_usuario", nome=nome_usuario())

    return falas.escolher(
        "generica"
    )

def eh_encerramento(texto):
    # A normalizacao remove pontuacao, entao "Tchau, Yasmin." vira
    # "tchau yasmin" e pode ser reconhecido de forma confiavel.
    t = normalizar(texto).strip()
    tokens = t.split()
    if not tokens:
        return False

    simples = {
        "tchau", "chau", "xau", "xauxau", "falou", "flw",
        "encerrar", "encerra", "desligar", "desliga", "desligue",
        "parar", "pare", "vou indo", "ja vou",
        "ate logo", "ate mais", "ate depois", "ate amanha",
        "nos vemos", "nos falamos",
    }
    if t in simples:
        return True

    nomes = {"yasm", "yas", "yasmin", "yasmim", "yasmine"}
    verbos = {"tchau", "chau", "xau", "xauxau", "falou", "flw",
              "encerrar", "encerra", "desligar", "desliga", "desligue",
              "parar", "pare", "vou indo", "ja vou", "ate logo", "ate mais"}

    if len(tokens) <= 4:
        if any(tok in nomes for tok in tokens) and any(tok in verbos for tok in tokens):
            return True

    return False


def resposta_fala(chave, **valores):
    """Ponto unico para qualquer novo comando obter linguagem da Yasm."""
    return falas.escolher(chave, **valores)
