import os
import re
import shutil
import subprocess
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path


# ============================================================
# APLICATIVOS DA YASM
# ============================================================
#
# Agora a Yasm pode abrir aplicativos apenas pelo nome.
#
# Exemplos:
#   "Opera"
#   "VS Code"
#   "IntelliJ"
#   "MySQL Workbench"
#   "Servidor Champ"
#   "Calculadora"
#
# Tambem aceitamos varias formas de o reconhecimento de voz
# escrever o nome do aplicativo.
# ============================================================

BASE = Path(__file__).resolve().parent


APLICATIVOS = {

    # --------------------------------------------------------
    # WINDOWS
    # --------------------------------------------------------

    "bloco de notas": {
        "aliases": (
            "bloco de notas",
            "bloco notas",
            "notepad",
            "notas",
            "bloco",
        ),
        "candidatos": (
            "notepad.exe",
        ),
    },

    "calculadora": {
        "aliases": (
            "calculadora",
            "calculo",
            "calc",
            "calculator",
        ),
        "candidatos": (
            "calc.exe",
        ),
    },

    "paint": {
        "aliases": (
            "paint",
            "mspaint",
            "pintura",
        ),
        "candidatos": (
            "mspaint.exe",
        ),
    },

    "explorador": {
        "aliases": (
            "explorador",
            "explorer",
            "explorador de arquivos",
            "arquivos",
            "gerenciador de arquivos",
            "meus arquivos",
        ),
        "candidatos": (
            "explorer.exe",
        ),
    },

    "prompt": {
        "aliases": (
            "cmd",
            "prompt",
            "terminal",
            "prompt de comando",
            "cmd prompt",
        ),
        "candidatos": (
            "cmd.exe",
        ),
    },

    "powershell": {
        "aliases": (
            "powershell",
            "power shell",
            "powers hell",
            "power shell",
        ),
        "candidatos": (
            "powershell.exe",
            "pwsh.exe",
        ),
    },

    "gerenciador de tarefas": {
        "aliases": (
            "gerenciador de tarefas",
            "gerenciador",
            "task manager",
            "gerenciador tarefas",
        ),
        "candidatos": (
            "taskmgr.exe",
        ),
    },

    "configuracoes": {
        "aliases": (
            "configuracoes",
            "configuracao",
            "settings",
            "configuracoes do windows",
        ),
        "candidatos": (
            "ms-settings:",
        ),
    },

    "terminal windows": {
        "aliases": (
            "terminal windows",
            "windows terminal",
            "terminal do windows",
            "wt",
        ),
        "candidatos": (
            "wt.exe",
        ),
    },

    # --------------------------------------------------------
    # NAVEGADOR
    # --------------------------------------------------------

    "chrome": {
        "aliases": (
            "chrome",
            "google chrome",
            "navegador chrome",
        ),
        "candidatos": (
            os.path.expandvars(
                r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
            ),
            os.path.expandvars(
                r"%LocalAppData%\Google\Chrome\Application\chrome.exe"
            ),
            "chrome.exe",
        ),
    },

    "edge": {
        "aliases": (
            "edge",
            "microsoft edge",
            "navegador edge",
        ),
        "candidatos": (
            os.path.expandvars(
                r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
            ),
            "msedge.exe",
        ),
    },

    "firefox": {
        "aliases": (
            "firefox",
            "mozilla firefox",
            "navegador firefox",
        ),
        "candidatos": (
            os.path.expandvars(
                r"%ProgramFiles%\Mozilla Firefox\firefox.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"
            ),
            "firefox.exe",
        ),
    },

    "opera": {
        "aliases": (
            "opera",
            "opera browser",
            "navegador opera",
            "opera gx",
            "opera g x",
            "opera gx browser",
        ),
        "candidatos": (
            os.path.expandvars(
                r"%ProgramFiles%\Opera\launcher.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles%\Opera GX\launcher.exe"
            ),
            os.path.expandvars(
                r"%LocalAppData%\Programs\Opera\launcher.exe"
            ),
            os.path.expandvars(
                r"%LocalAppData%\Programs\Opera GX\launcher.exe"
            ),
            "opera.exe",
            "launcher.exe",
        ),
    },

    # --------------------------------------------------------
    # PROGRAMACAO
    # --------------------------------------------------------

    "vscode": {
        "aliases": (
            "vscode",
            "vs code",
            "visual studio code",
            "visual studio",
            "vs code studio",
            "visual studio code",
        ),
        "candidatos": (
            os.path.expandvars(
                r"%LocalAppData%\Programs\Microsoft VS Code\Code.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles%\Microsoft VS Code\Code.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles(x86)%\Microsoft VS Code\Code.exe"
            ),
            "code.exe",
        ),
    },

    "pycharm": {
        "aliases": (
            "pycharm",
            "pie charm",
            "jetbrains pycharm",
        ),
        "candidatos": (
            os.path.expandvars(
                r"%ProgramFiles%\JetBrains\PyCharm Community Edition\bin\pycharm64.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles%\JetBrains\PyCharm\bin\pycharm64.exe"
            ),
            os.path.expandvars(
                r"%LocalAppData%\Programs\PyCharm Community Edition\bin\pycharm64.exe"
            ),
            "pycharm64.exe",
            "pycharm.exe",
        ),
    },

    "python idle": {
        "aliases": (
            "idle",
            "python idle",
            "idle python",
        ),
        "candidatos": (
            "idle.exe",
            "idle3.exe",
        ),
    },

    "intellij": {
        "aliases": (
            "intellij",
            "intelij",
            "intelij idea",
            "intellij idea",
            "inteli j",
            "inteli j idea",
            "intelijidea",
            "jetbrains intellij",
            "jetbrains idea",
            "idea",
            "idea64",
        ),
        "candidatos": (
            os.path.expandvars(
                r"%ProgramFiles%\JetBrains\IntelliJ IDEA Community Edition\bin\idea64.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles%\JetBrains\IntelliJ IDEA\bin\idea64.exe"
            ),
            os.path.expandvars(
                r"%LocalAppData%\Programs\IntelliJ IDEA Community Edition\bin\idea64.exe"
            ),
            os.path.expandvars(
                r"%LocalAppData%\Programs\IntelliJ IDEA\bin\idea64.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles%\JetBrains\JetBrains IntelliJ IDEA Community Edition\bin\idea64.exe"
            ),
            "idea64.exe",
            "idea.exe",
        ),
    },

    # --------------------------------------------------------
    # BANCO DE DADOS
    # --------------------------------------------------------

    "mysql workbench": {
        "aliases": (
            "mysql workbench",
            "mysql work bench",
            "mysql",
            "workbench",
            "work bench",
            "mysqlworkbench",
            "mysql workbenche",
            "mysql workbanch",
            "mysql workbench",
        ),
        "candidatos": (
            os.path.expandvars(
                r"%ProgramFiles%\MySQL\MySQL Workbench 8.0\MySQLWorkbench.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles%\MySQL\MySQL Workbench 8.0 CE\MySQLWorkbench.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles(x86)%\MySQL\MySQL Workbench 8.0\MySQLWorkbench.exe"
            ),
            "MySQLWorkbench.exe",
            "mysqlworkbench.exe",
        ),
    },

    # --------------------------------------------------------
    # XAMPP
    # --------------------------------------------------------
    #
    # O nome principal que a Yasm vai usar e "servidor champ".
    # Colocamos varias formas porque o reconhecimento pode
    # distorcer "XAMPP" de varias maneiras.
    # --------------------------------------------------------

    "servidor champ": {
        "aliases": (
            "servidor champ",
            "servidor xampp",
            "servidor champ",
            "server champ",
            "server xampp",
            "xampp",
            "xamp",
            "zamp",
            "zamp server",
            "zamp servidor",
            "champ",
            "champ servidor",
            "servidor samp",
            "servidor zamp",
            "xam",
            "xamp servidor",
            "servidor examp",
            "servidor samp",
            "xampp servidor",
        ),
        "candidatos": (
            os.path.expandvars(
                r"%ProgramFiles%\XAMPP\xampp-control.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles(x86)%\XAMPP\xampp-control.exe"
            ),
            os.path.expandvars(
                r"%SystemDrive%\xampp\xampp-control.exe"
            ),
            os.path.expandvars(
                r"%SystemDrive%\xampp\xampp-control.exe"
            ),
            "xampp-control.exe",
        ),
    },

    # --------------------------------------------------------
    # OUTROS
    # --------------------------------------------------------

    "steam": {
        "aliases": (
            "steam",
            "steam da valve",
            "valve steam",
        ),
        "candidatos": (
            os.path.expandvars(
                r"%ProgramFiles(x86)%\Steam\steam.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles%\Steam\steam.exe"
            ),
            os.path.expandvars(
                r"%LocalAppData%\Programs\Steam\steam.exe"
            ),
            "steam.exe",
        ),
    },

    "discord": {
        "aliases": (
            "discord",
        ),
        "candidatos": (
            os.path.expandvars(
                r"%LocalAppData%\Discord\Update.exe"
            ),
            os.path.expandvars(
                r"%LocalAppData%\Programs\Discord\Discord.exe"
            ),
            "Discord.exe",
        ),
    },

    "spotify": {
        "aliases": (
            "spotify",
        ),
        "candidatos": (
            os.path.expandvars(
                r"%AppData%\Spotify\Spotify.exe"
            ),
            os.path.expandvars(
                r"%LocalAppData%\Microsoft\WindowsApps\Spotify.exe"
            ),
            "Spotify.exe",
        ),
    },

    "word": {
        "aliases": (
            "word",
            "microsoft word",
        ),
        "candidatos": (
            "winword.exe",
        ),
    },

    "excel": {
        "aliases": (
            "excel",
            "microsoft excel",
        ),
        "candidatos": (
            "excel.exe",
        ),
    },

    "powerpoint": {
        "aliases": (
            "powerpoint",
            "power point",
            "microsoft powerpoint",
        ),
        "candidatos": (
            "powerpnt.exe",
        ),
    },

}



# Processos que podem ser encerrados com seguranca pela Yasm.
PROCESSOS = {
    "bloco de notas": ("notepad.exe",),
    "calculadora": ("CalculatorApp.exe", "calc.exe"),
    "paint": ("mspaint.exe",),
    "explorador": ("explorer.exe",),
    "prompt": ("cmd.exe",),
    "powershell": ("powershell.exe", "pwsh.exe"),
    "terminal windows": ("WindowsTerminal.exe", "wt.exe"),
    "gerenciador de tarefas": ("Taskmgr.exe",),
    "chrome": ("chrome.exe",),
    "edge": ("msedge.exe",),
    "firefox": ("firefox.exe",),
    "opera": ("opera.exe",),
    "vscode": ("Code.exe", "code.exe", "Code - Insiders.exe"),
    "pycharm": ("pycharm64.exe", "pycharm.exe"),
    "python idle": ("idle.exe", "idle3.exe"),
    "intellij": ("idea64.exe", "idea.exe"),
    "mysql workbench": ("MySQLWorkbench.exe",),
    "servidor champ": ("xampp-control.exe",),
    "steam": ("steam.exe",),
    "discord": ("Discord.exe",),
    "spotify": ("Spotify.exe",),
    "word": ("WINWORD.EXE", "winword.exe"),
    "excel": ("EXCEL.EXE", "excel.exe"),
    "powerpoint": ("POWERPNT.EXE", "powerpnt.exe"),
}


# ============================================================
# FRASES PREDEFINIDAS / ATALHOS
# ============================================================
#
# Estes atalhos sao executados antes do reconhecimento de
# aplicativos individuais. Isso evita depender da transcricao
# perfeita de nomes como IntelliJ ou XAMPP.
#
# Exemplos:
#   "programar java"
#   "programar"
#   "bd"
#
# Cada frase abre uma sequencia de aplicativos.
# ============================================================

ATALHOS = {
    "programar java": (
        "explorador",
        "opera",
        "intellij",
        "vscode",
    ),

    "programar": (
        "explorador",
        "opera",
        "vscode",
    ),

    "bd": (
        "servidor champ",
        "mysql workbench",
    ),
}


def _executar_lista_aplicativos(nomes):
    """
    Abre uma sequencia de aplicativos.

    Continua tentando os proximos mesmo se um aplicativo
    nao estiver instalado.
    """
    resultados = []

    for nome in nomes:
        try:
            resposta = abrir_aplicativo(nome)
            resultados.append(resposta)
        except Exception as erro:
            resultados.append(
                f"Nao consegui abrir {nome}: "
                f"{type(erro).__name__}."
            )

    return resultados


def identificar_atalho(texto: str):
    """
    Identifica uma frase predefinida.

    Prioriza frases maiores para evitar conflito.
    """
    texto = _normalizar(texto)

    if not texto:
        return None

    encontrados = []

    for frase in ATALHOS:
        frase_n = _normalizar(frase)

        if texto == frase_n:
            encontrados.append(
                (len(frase_n), frase)
            )

    if not encontrados:
        return None

    encontrados.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return encontrados[0][1]


def comando_atalho(texto: str):
    """
    Executa uma frase predefinida.

    Exemplos:
        programar java
        programar
        bd
    """
    atalho = identificar_atalho(texto)

    if not atalho:
        return None

    aplicativos = ATALHOS[atalho]

    resultados = _executar_lista_aplicativos(
        aplicativos
    )

    return " ".join(resultado for resultado in resultados if resultado)


def listar_atalhos():
    """Retorna os atalhos disponiveis."""
    return tuple(ATALHOS.keys())


# ============================================================
# NORMALIZACAO
# ============================================================

def _normalizar(texto: str) -> str:
    texto = str(texto or "").lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    texto = re.sub(
        r"[^\w\s]",
        " ",
        texto,
        flags=re.UNICODE,
    )

    return " ".join(texto.split())


def _tem_gatilho_abrir(texto: str) -> bool:
    gatilhos = (
        "abrir",
        "abra",
        "abre",
        "iniciar",
        "inicia",
        "executar",
        "execute",
        "rodar",
        "rode",
        "ligar",
        "liga",
    )
    return any(
        f" {gatilho} " in f" {texto} "
        for gatilho in gatilhos
    )


def _tem_gatilho_fechar(texto: str) -> bool:
    gatilhos = (
        "fechar",
        "fecha",
        "feche",
        "encerrar",
        "encerra",
        "sair do",
        "sair da",
        "pare",
        "parar",
    )
    return any(
        f" {gatilho} " in f" {texto} "
        for gatilho in gatilhos
    )


def _texto_sem_gatilho(texto: str) -> str:
    texto_n = _normalizar(texto)
    padroes = (
        "por favor",
        "pode",
        "voce pode",
        "abrir",
        "abra",
        "abre",
        "abrir o",
        "abrir a",
        "abra o",
        "abra a",
        "abre o",
        "abre a",
        "iniciar",
        "inicia",
        "executar",
        "execute",
        "rodar",
        "rode",
        "ligar",
        "liga",
        "fechar",
        "fecha",
        "feche",
        "encerrar",
        "encerra",
        "sair do",
        "sair da",
        "pare",
        "parar",
        "aplicativo",
        "programa",
        "app",
        "o",
        "a",
    )

    mudou = True
    while mudou:
        mudou = False
        for padrao in padroes:
            if texto_n == padrao:
                return ""
            if texto_n.startswith(padrao + " "):
                texto_n = texto_n[len(padrao):].strip()
                mudou = True

    return texto_n


def _pastas_do_windows():
    caminhos = (
        r"%ProgramData%\Microsoft\Windows\Start Menu\Programs",
        r"%AppData%\Microsoft\Windows\Start Menu\Programs",
        r"%UserProfile%\Desktop",
        r"%Public%\Desktop",
        r"%LocalAppData%\Microsoft\WindowsApps",
    )

    for caminho in caminhos:
        pasta = Path(os.path.expandvars(caminho))
        if pasta.exists():
            yield pasta


@lru_cache(maxsize=1)
def aplicativos_instalados():
    encontrados = {}
    extensoes = {".lnk", ".exe", ".url", ".appref-ms"}

    for pasta in _pastas_do_windows():
        try:
            arquivos = pasta.rglob("*")
        except OSError:
            continue

        for arquivo in arquivos:
            try:
                if not arquivo.is_file():
                    continue
                if arquivo.suffix.lower() not in extensoes:
                    continue
            except OSError:
                continue

            nome = arquivo.stem
            nome_n = _normalizar(nome)

            if not nome_n or len(nome_n) < 2:
                continue

            encontrados.setdefault(nome_n, str(arquivo))

    return encontrados


def _pontuar_app(consulta: str, nome: str) -> float:
    consulta = _normalizar(consulta)
    nome = _normalizar(nome)

    if not consulta or not nome:
        return 0.0

    if consulta == nome:
        return 1.0

    if consulta in nome:
        return 0.88 if len(consulta) >= 4 else 0.0

    if nome in consulta:
        return 0.84 if len(nome) >= 4 else 0.0

    return SequenceMatcher(None, consulta, nome).ratio()


def _encontrar_app_instalado(consulta: str):
    consulta = _texto_sem_gatilho(consulta)

    if not consulta:
        return None

    instalados = aplicativos_instalados()
    melhor = None
    melhor_score = 0.0

    for nome, caminho in instalados.items():
        score = _pontuar_app(consulta, nome)

        if score > melhor_score:
            melhor = (nome, caminho)
            melhor_score = score

    if melhor and melhor_score >= 0.82:
        return {
            "nome": melhor[0],
            "caminho": melhor[1],
            "score": melhor_score,
        }

    return None


def _abrir_caminho(caminho: str):
    if caminho.startswith("ms-"):
        os.startfile(caminho)
        return

    path = Path(caminho)

    if path.exists() and path.suffix.lower() in {".lnk", ".url", ".appref-ms"}:
        os.startfile(str(path))
        return

    if path.exists():
        subprocess.Popen(
            [str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return

    executavel = shutil.which(caminho)

    if executavel:
        subprocess.Popen(
            [executavel],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return

    try:
        os.startfile(caminho)
        return
    except OSError:
        pass

    subprocess.Popen(
        [caminho],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


# ============================================================
# ENCONTRAR EXECUTAVEL
# ============================================================

def _encontrar_executavel(candidatos):
    fallback = None
    for candidato in candidatos:

        if not candidato:
            continue

        if str(candidato).startswith("ms-"):
            return str(candidato)

        caminho = Path(candidato)

        # Caminho absoluto/existente.
        if caminho.exists():
            return str(caminho)

        # Nome disponivel no PATH do Windows.
        if not caminho.is_absolute():
            encontrado = shutil.which(candidato)
            if encontrado:
                return encontrado
            # Alguns aplicativos sao resolvidos pelo Windows fora do PATH.
            # So tente esse nome depois de conferir os demais candidatos.
            if fallback is None:
                fallback = candidato

    return fallback


# ============================================================
# ABRIR
# ============================================================

def abrir_aplicativo(nome: str):
    """Abre um aplicativo pelo nome canonico."""

    chave = _normalizar(nome)

    if chave not in APLICATIVOS:
        instalado = _encontrar_app_instalado(chave)

        if not instalado:
            return f"Eu ainda nao sei abrir o aplicativo {nome}."

        try:
            _abrir_caminho(instalado["caminho"])
            return f"Abrindo {instalado['nome']}."
        except Exception as erro:
            return (
                f"Nao consegui abrir {instalado['nome']}: "
                f"{type(erro).__name__}."
            )

    dados = APLICATIVOS[chave]

    executavel = _encontrar_executavel(
        dados["candidatos"]
    )

    if not executavel:
        instalado = _encontrar_app_instalado(chave)
        if instalado:
            try:
                _abrir_caminho(instalado["caminho"])
                return f"Abrindo {instalado['nome']}."
            except OSError as erro:
                return f"Nao consegui abrir {chave}: {type(erro).__name__}."
        return (
            f"Nao encontrei o executavel do "
            f"{chave} neste computador."
        )

    try:
        _abrir_caminho(executavel)

        return f"Abrindo {chave}."

    except OSError:

        try:
            instalado = _encontrar_app_instalado(chave)

            if instalado:
                _abrir_caminho(instalado["caminho"])
                return f"Abrindo {instalado['nome']}."

            os.startfile(executavel)

            return f"Abrindo {chave}."

        except Exception as erro:

            return (
                f"Nao consegui abrir {chave}: "
                f"{type(erro).__name__}."
            )


# ============================================================
# FECHAR APLICATIVO
# ============================================================

def _encerrar_processo(processo: str) -> bool:
    """Tenta encerrar o processo e toda a arvore de processos."""
    try:
        resultado = subprocess.run(
            ["taskkill", "/IM", processo, "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
            text=True,
        )
        return resultado.returncode == 0
    except Exception:
        return False


def fechar_aplicativo(nome: str):
    """Fecha um aplicativo pelo nome usando taskkill no Windows."""
    chave = _normalizar(nome)

    if chave not in APLICATIVOS:
        return f"Eu ainda nao sei fechar o aplicativo {nome}."

    processos = PROCESSOS.get(chave, ())
    if not processos:
        return f"Nao tenho um processo configurado para fechar {chave}."

    fechou = False

    for processo in processos:
        if _encerrar_processo(processo):
            fechou = True

    if fechou:
        return f"Fechando {chave}."

    # Alguns aplicativos iniciam processos auxiliares.
    # Tentamos novamente com nomes alternativos mais comuns.
    alternativos = {
        "vscode": ("Code.exe", "Code - Insiders.exe"),
        "opera": ("opera.exe",),
        "intellij": ("idea64.exe", "idea.exe"),
        "mysql workbench": ("MySQLWorkbench.exe",),
    }

    for processo in alternativos.get(chave, ()):
        if _encerrar_processo(processo):
            return f"Fechando {chave}."

    return f"O {chave} nao esta aberto."


def comando_fechar_aplicativo(texto: str):
    """Fecha apps com frases como 'fecha VS Code' ou apenas 'fecha Opera'."""
    texto_n = _normalizar(texto)

    if not texto_n:
        return None

    gatilhos = (
        "fechar", "fecha", "feche",
        "encerrar aplicativo", "encerra aplicativo",
        "pare o aplicativo", "parar aplicativo",
        "feche o aplicativo", "fecha o aplicativo",
    )

    tem_gatilho = _tem_gatilho_fechar(texto_n)

    if not tem_gatilho:
        return None

    aplicativo = identificar_aplicativo(texto_n)
    if not aplicativo:
        return None

    return fechar_aplicativo(aplicativo)


# ============================================================
# IDENTIFICAR APLICATIVO
# ============================================================

def identificar_aplicativo(texto: str):
    """
    Identifica o aplicativo citado.

    A prioridade e por alias mais longo para evitar conflitos.
    """

    texto = _normalizar(texto)
    consulta = _texto_sem_gatilho(texto)
    tem_gatilho = _tem_gatilho_abrir(texto) or _tem_gatilho_fechar(texto)
    texto_alvo = consulta if tem_gatilho and consulta else texto
    aliases_genericos = {
        "notas",
        "tarefas",
        "arquivos",
        "terminal",
        "prompt",
        "gerenciador",
        "calculo",
        "bloco",
    }

    encontrados = []

    for nome, dados in APLICATIVOS.items():

        for alias in dados["aliases"]:

            alias_n = _normalizar(alias)

            if not alias_n:
                continue

            exato = texto_alvo == alias_n
            contido = f" {alias_n} " in f" {texto_alvo} "

            if alias_n in aliases_genericos and not exato and not tem_gatilho:
                continue

            if exato or (contido and tem_gatilho):

                encontrados.append(
                    (
                        len(alias_n) + (1000 if exato else 0),
                        nome
                    )
                )

    if not encontrados:
        instalado = _encontrar_app_instalado(texto_alvo)

        if instalado:
            return instalado["nome"]

        return None

    encontrados.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return encontrados[0][1]


# ============================================================
# COMANDO
# ============================================================

def comando_abrir_aplicativo(texto: str):
    """
    Abre o aplicativo citado.

    Agora nao e necessario falar "abrir".
    Basta dizer o nome:

        Opera
        IntelliJ
        MySQL Workbench
        servidor champ
        VS Code

    Tambem aceita frases normais como:

        abre o Opera
        pode abrir o IntelliJ
        inicia o servidor champ
    """

    texto_n = _normalizar(texto)

    if not texto_n:
        return None

    if _tem_gatilho_fechar(texto_n):
        return None

    # Sem um verbo de abertura, so aceitamos nomes curtos de aplicativos.
    # Isso evita abrir Python ao ouvir "me explique listas em Python".
    if not _tem_gatilho_abrir(texto_n) and len(texto_n.split()) > 3:
        return None

    aplicativo = identificar_aplicativo(
        texto_n
    )

    if not aplicativo:
        return None

    return abrir_aplicativo(
        aplicativo
    )


# ============================================================
# LISTAR APLICATIVOS
# ============================================================

def listar_aplicativos():
    """Retorna os nomes canonicos conhecidos pela Yasm."""

    nomes = list(APLICATIVOS.keys())

    try:
        nomes.extend(list(aplicativos_instalados().keys())[:80])
    except Exception:
        pass

    return tuple(dict.fromkeys(nomes))
