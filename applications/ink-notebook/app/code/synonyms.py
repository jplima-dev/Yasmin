"""Ponte entre a linguagem natural (pt-BR) e nomes de código. Edite à vontade: frase -> termos de código."""
PHRASES = {
    "caixa preta": ["blackbox", "black-box"], "caixa-preta": ["blackbox"],
    "modulo": ["module"], "modulos": ["module"], "tema": ["theme"], "botao": ["button", "btn"],
    "configuracao": ["config", "settings"],
    "configuracoes": ["config", "settings"], "banco": ["db", "database"], "rota": ["route"],
    "busca": ["search"], "pesquisa": ["search"], "indice": ["index"], "armazenamento": ["storage"],
    "atividade": ["activity"], "diagnostico": ["diagnostic"], "falha": ["error", "fail"], "erro": ["error"],
    "carregar": ["load", "loader"], "carregamento": ["load", "loader"], "registrar": ["register"],
    "registro": ["registry", "register"], "servidor": ["server"], "usuario": ["user"], "notas": ["note"],
    "caderno": ["notebook"], "cadernos": ["notebook"], "clico": ["click", "onclick"], "clicar": ["click"],
    "evento": ["event"], "janela": ["window", "dialog"], "estilo": ["style", "css"],
}


def expand(folded_query: str):
    """Termos extras (já em minúsculas, sem acento) que ajudam a achar nomes de código."""
    extra = []
    for phrase, terms in PHRASES.items():
        if phrase in folded_query:
            extra += terms
    return list(dict.fromkeys(extra))

QUESTION_WORDS = set("""onde como qual quais quem quando porque por que fica ficam esta estao existem tem possui eu me mostra
mostre mostrar explica explique isso esse essa aqui controla controlam arquivo arquivos projeto pode posso preciso precisaria
faco faz funciona acontece envolvidos responsavel todos todas coloco colocar adiciono adicionar criar novo nova outro outra
igual sistema diga fala""".split())
