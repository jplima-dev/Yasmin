"""
Utilitários compartilhados para leitura de projetos.

Responsabilidades:
- Resolver caminhos dinâmicos (Desktop com/sem OneDrive), sem depender
  do diretório de execução (necessário para builds PyInstaller).
- Centralizar a detecção de arquivos sensíveis (.env, chaves, tokens),
  para que separado.py e junto.py usem exatamente a mesma regra.
"""

from __future__ import annotations

import os
from pathlib import Path


class FiltroIgnorados:
    """Nomes valem em qualquer pasta; caminhos são relativos ao projeto.

    './build' ignora só build na raiz; 'build' ignora todas desse nome.
    Aceita também caminhos absolutos e barras do Windows.
    """

    def __init__(self, regras: list[str], raiz: str):
        self.raiz = os.path.abspath(raiz)
        self.nomes: set[str] = set()
        self.caminhos: set[str] = set()
        for regra in regras:
            valor = regra.strip().replace("\\", "/")
            if not valor:
                continue
            if "/" not in valor and not os.path.isabs(valor):
                self.nomes.add(valor.lower())
            else:
                alvo = valor if os.path.isabs(valor) else os.path.join(self.raiz, valor)
                self.caminhos.add(os.path.normpath(alvo).replace("\\", "/").lower())

    def corresponde(self, caminho: str | Path) -> bool:
        caminho = os.fspath(caminho)
        return (os.path.basename(caminho).lower() in self.nomes
                or os.path.abspath(caminho).replace("\\", "/").lower() in self.caminhos)

# Nomes de arquivo que NUNCA devem ser processados, independente de
# extensão configurada pelo usuário. Comparação é feita em minúsculas.
NOMES_SENSIVEIS_EXATOS = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_rsa.pub",
    "id_ed25519",
}

# Padrões (substring no nome do arquivo, minúsculo) que indicam
# possível conteúdo sensível. Usado apenas para o aviso "Serão
# processados X arquivos, sensíveis ignorados: Y" — não é análise
# de conteúdo, só de nome, para manter o processamento rápido e
# simples conforme pedido na spec.
PADROES_SENSIVEIS_SUBSTRING = (
    "secret",
    "senha",
    "password",
    "token",
    "apikey",
    "api_key",
    "credential",
)


def obter_desktop() -> Path:
    """
    Retorna o caminho do Desktop do usuário atual, funcionando tanto
    com OneDrive quanto sem, e independente do nome do usuário do
    Windows. Nunca hardcoda caminho de usuário específico.
    """
    home = Path.home()
    desktop_onedrive = home / "OneDrive" / "Desktop"
    if desktop_onedrive.exists():
        return desktop_onedrive
    desktop_padrao = home / "Desktop"
    return desktop_padrao


def obter_pasta_saida_padrao() -> Path:
    """
    Pasta de saída padrão quando o usuário não escolhe uma:
    <Desktop>/Leitor de Projetos/
    """
    pasta = obter_desktop() / "Leitor de Projetos"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def eh_arquivo_sensivel(nome_arquivo: str) -> bool:
    """
    Verifica se um arquivo é considerado sensível pelo NOME (não lê
    o conteúdo). Usado para bloquear .env e afins mesmo que a
    extensão do arquivo esteja na lista de extensões permitidas.

    Esta é a checagem que os scripts originais NÃO faziam de forma
    confiável: eles só ignoravam ".env" quando ele aparecia como
    nome de PASTA (via os.path.isdir), então um arquivo chamado
    ".env" na raiz do projeto passava despercebido se sua extensão
    (inexistente/".env") não caísse na lista de EXTENSOES já
    filtrada — o que na prática dependia de sorte de configuração.
    Aqui a checagem é sempre por nome, antes de qualquer outra regra.
    """
    nome_lower = nome_arquivo.lower()

    if (nome_lower in NOMES_SENSIVEIS_EXATOS or nome_lower.startswith(".env.")
            or nome_lower.endswith(".pem")):
        return True

    for padrao in PADROES_SENSIVEIS_SUBSTRING:
        if padrao in nome_lower:
            return True

    return False


def caminho_relativo_seguro(caminho_completo: str, raiz: str) -> str:
    """
    Retorna o caminho relativo à raiz do projeto, para exibição.
    Nunca expõe o caminho absoluto completo do computador do usuário
    em logs/históricos que possam ser compartilhados.
    """
    try:
        return os.path.relpath(caminho_completo, raiz)
    except ValueError:
        # Pode ocorrer em Windows se os caminhos estiverem em drives
        # diferentes; nesse caso cai para o nome do arquivo apenas.
        return os.path.basename(caminho_completo)
