"""
Configurações persistentes do usuário.

Salva em %APPDATA%/LeitorDeProjetos/config.json (Windows) ou
~/.config/LeitorDeProjetos/config.json (outros sistemas, útil para
testes fora do Windows). Nunca depende do diretório de execução do
programa, para funcionar corretamente após empacotamento com
PyInstaller.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

NOME_APP = "LeitorDeProjetos"

EXTENSOES_PADRAO_SEPARADO = [
    ".php", ".css", ".js", ".py", ".html", ".txt", ".bat", ".md",
]

EXTENSOES_PADRAO_JUNTO = [
    ".php", ".css", ".js",
]

PASTAS_IGNORADAS_PADRAO = [
    "vendor",
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "Lib",
    "Include",
    "Scripts",
    ".idea",
    ".vscode",
]

ARQUIVOS_IGNORADOS_PADRAO = [
    ".env",
    ".gitignore",
]

CONFIG_PADRAO: dict[str, Any] = {
    "ultima_pasta_projeto": "",
    "ultima_pasta_saida": "",
    "ultimo_modo": "separado",  # "separado" = arquivo único | "junto" = arquivos separados
    "extensoes_separado": list(EXTENSOES_PADRAO_SEPARADO),
    "extensoes_junto": list(EXTENSOES_PADRAO_JUNTO),
    "pastas_ignoradas": list(PASTAS_IGNORADAS_PADRAO),
    "arquivos_ignorados": list(ARQUIVOS_IGNORADOS_PADRAO),
    "janela_largura": 900,
    "janela_altura": 640,
    "idioma": "pt_BR",
    "ia_limite_tokens": 30000,
    "ia_formato": "Markdown",
    "ia_incluir_arvore": True,
    "ia_dividir": True,
}


def obter_diretorio_config() -> Path:
    """
    Diretório onde a configuração é salva. Usa APPDATA no Windows
    (padrão do sistema para dados de app por usuário), com fallback
    para ~/.config em outros sistemas operacionais.
    """
    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata)
    else:
        base = Path.home() / ".config"
    return base / NOME_APP


def obter_caminho_config() -> Path:
    return obter_diretorio_config() / "config.json"


def carregar_config() -> dict[str, Any]:
    """
    Carrega a configuração salva, mesclando com os padrões (para que
    novas chaves adicionadas em versões futuras não quebrem configs
    antigas). Se o arquivo não existir ou estiver corrompido, retorna
    os padrões.
    """
    caminho = obter_caminho_config()
    config = deepcopy(CONFIG_PADRAO)

    if not caminho.exists():
        return config

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            salvo = json.load(f)
        if isinstance(salvo, dict):
            config.update(salvo)
    except (json.JSONDecodeError, OSError):
        # Config corrompida: usa padrões em vez de travar a aplicação.
        pass

    return config


def salvar_config(config: dict[str, Any]) -> None:
    """
    Salva a configuração no disco. Nunca inclui conteúdo de projetos
    ou arquivos processados — apenas preferências (caminhos,
    extensões, listas de ignorados, modo).
    """
    diretorio = obter_diretorio_config()
    diretorio.mkdir(parents=True, exist_ok=True)
    caminho = obter_caminho_config()

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def restaurar_extensoes_padrao(modo: str) -> list[str]:
    if modo == "separado":
        return list(EXTENSOES_PADRAO_SEPARADO)
    return list(EXTENSOES_PADRAO_JUNTO)


def restaurar_pastas_ignoradas_padrao() -> list[str]:
    return list(PASTAS_IGNORADAS_PADRAO)
