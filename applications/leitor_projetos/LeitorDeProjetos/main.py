"""
Leitor de Projetos — entrypoint.

Transforma projetos de código em arquivos de texto, para análise,
documentação, compartilhamento e uso com IAs.
"""

from __future__ import annotations

import os
import sys

# Garante que os pacotes internos (interface, processadores,
# configuracao, utils) sejam encontrados independentemente de onde o
# programa é executado — necessário tanto para execução direta
# (python main.py de qualquer diretório) quanto para o executável
# gerado pelo PyInstaller (sys._MEIPASS aponta para os recursos
# extraídos temporariamente).
if getattr(sys, "frozen", False):
    DIRETORIO_BASE = sys._MEIPASS  # type: ignore[attr-defined]
else:
    DIRETORIO_BASE = os.path.dirname(os.path.abspath(__file__))

if DIRETORIO_BASE not in sys.path:
    sys.path.insert(0, DIRETORIO_BASE)

from interface.janela_principal import JanelaPrincipal  # noqa: E402


def main() -> None:
    app = JanelaPrincipal()
    app.mainloop()


if __name__ == "__main__":
    main()
