"""
Janela de configurações: idioma, extensões por modo, pastas ignoradas
e arquivos ignorados. Alterações são persistidas ao fechar a janela.
"""

from __future__ import annotations

from copy import deepcopy
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable

from configuracao.config import (
    restaurar_extensoes_padrao,
    restaurar_pastas_ignoradas_padrao,
)
from configuracao.idiomas import IDIOMA_PADRAO, NOMES_IDIOMAS, traduzir

from interface.estilo import (
    COR_FUNDO, COR_FUNDO_CARD, COR_TEXTO, COR_TEXTO_SECUNDARIO, COR_ERRO, COR_DESTAQUE,
)

ARQUIVO_PROTEGIDO = ".env"


class JanelaConfiguracoes(tk.Toplevel):
    def __init__(self, parent: tk.Widget, config: dict, on_salvar: Callable[[dict], None]):
        super().__init__(parent)

        self._config = deepcopy(config)
        self._on_salvar = on_salvar
        self._idioma_atual = self._config.get("idioma", IDIOMA_PADRAO)
        self._idioma = tk.StringVar(value=self._idioma_atual)

        self.title(traduzir("titulo_configuracoes", self._idioma_atual))
        self.configure(bg=COR_FUNDO)
        self.transient(parent)
        self.grab_set()
        self.geometry("580x600")
        self.protocol("WM_DELETE_WINDOW", self._fechar)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=16, pady=16)

        aba_extensoes = tk.Frame(notebook, bg=COR_FUNDO)
        aba_ignorados = tk.Frame(notebook, bg=COR_FUNDO)
        aba_idioma = tk.Frame(notebook, bg=COR_FUNDO)

        notebook.add(aba_extensoes, text=traduzir("aba_extensoes", self._idioma_atual))
        notebook.add(aba_ignorados, text=traduzir("aba_ignorados", self._idioma_atual))
        notebook.add(aba_idioma, text=traduzir("aba_idioma", self._idioma_atual))

        self._montar_aba_extensoes(aba_extensoes)
        self._montar_aba_ignorados(aba_ignorados)
        self._montar_aba_idioma(aba_idioma)

        tk.Button(
            self,
            text=traduzir("fechar", self._idioma_atual),
            command=self._fechar,
            bg=COR_FUNDO_CARD,
            fg=COR_TEXTO,
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
        ).pack(pady=(0, 16))

    def _t(self, chave: str, **valores: object) -> str:
        return traduzir(chave, self._idioma_atual, **valores)

    # ---------------- Extensões ----------------

    def _montar_aba_extensoes(self, aba: tk.Frame) -> None:
        for modo, chave, titulo in [
            ("separado", "extensoes_separado", self._t("modo_arquivo_unico_titulo")),
            ("junto", "extensoes_junto", self._t("modo_arquivos_separados_titulo")),
        ]:
            secao = tk.Frame(aba, bg=COR_FUNDO)
            secao.pack(fill="x", padx=16, pady=(16, 8))

            tk.Label(
                secao,
                text=titulo,
                font=("Segoe UI", 10, "bold"),
                bg=COR_FUNDO,
                fg=COR_TEXTO,
            ).pack(anchor="w")

            corpo = tk.Frame(secao, bg=COR_FUNDO)
            corpo.pack(fill="x", pady=(6, 0))

            lista = tk.Listbox(
                corpo,
                height=5,
                bg=COR_FUNDO_CARD,
                fg=COR_TEXTO,
                selectbackground=COR_DESTAQUE,
                borderwidth=0,
                highlightthickness=0,
                font=("Consolas", 9),
            )
            lista.pack(side="left", fill="both", expand=True)
            for ext in self._config[chave]:
                lista.insert("end", ext)

            botoes = tk.Frame(corpo, bg=COR_FUNDO)
            botoes.pack(side="left", padx=(8, 0))

            tk.Button(
                botoes,
                text=self._t("adicionar"),
                width=14,
                command=lambda l=lista, c=chave: self._adicionar_extensao(l, c),
                bg=COR_FUNDO_CARD,
                fg=COR_TEXTO,
                relief="flat",
                cursor="hand2",
            ).pack(pady=2)
            tk.Button(
                botoes,
                text=self._t("remover"),
                width=14,
                command=lambda l=lista, c=chave: self._remover_selecionado(l, c),
                bg=COR_FUNDO_CARD,
                fg=COR_TEXTO,
                relief="flat",
                cursor="hand2",
            ).pack(pady=2)
            tk.Button(
                botoes,
                text=self._t("restaurar_padrao"),
                width=14,
                command=lambda l=lista, c=chave, m=modo: self._restaurar_extensoes(l, c, m),
                bg=COR_FUNDO_CARD,
                fg=COR_TEXTO_SECUNDARIO,
                relief="flat",
                cursor="hand2",
            ).pack(pady=2)

    def _adicionar_extensao(self, lista: tk.Listbox, chave: str) -> None:
        valor = simpledialog.askstring(
            self._t("adicionar_extensao"),
            self._t("extensao_exemplo"),
            parent=self,
        )
        if not valor:
            return
        valor = valor.strip()
        if not valor.startswith("."):
            valor = "." + valor
        if valor not in self._config[chave]:
            self._config[chave].append(valor)
            lista.insert("end", valor)

    def _remover_selecionado(self, lista: tk.Listbox, chave: str) -> None:
        selecao = lista.curselection()
        if not selecao:
            return
        indice = selecao[0]
        valor = lista.get(indice)
        lista.delete(indice)
        if valor in self._config[chave]:
            self._config[chave].remove(valor)

    def _restaurar_extensoes(self, lista: tk.Listbox, chave: str, modo: str) -> None:
        padrao = restaurar_extensoes_padrao(modo)
        self._config[chave] = list(padrao)
        lista.delete(0, "end")
        for ext in padrao:
            lista.insert("end", ext)

    # ---------------- Pastas e arquivos ignorados ----------------

    def _montar_aba_ignorados(self, aba: tk.Frame) -> None:
        secao_pastas = tk.Frame(aba, bg=COR_FUNDO)
        secao_pastas.pack(fill="x", padx=16, pady=(16, 8))

        tk.Label(
            secao_pastas,
            text=self._t("pastas_ignoradas"),
            font=("Segoe UI", 10, "bold"),
            bg=COR_FUNDO,
            fg=COR_TEXTO,
        ).pack(anchor="w")

        corpo_pastas = tk.Frame(secao_pastas, bg=COR_FUNDO)
        corpo_pastas.pack(fill="x", pady=(6, 0))

        self._lista_pastas = tk.Listbox(
            corpo_pastas,
            height=6,
            bg=COR_FUNDO_CARD,
            fg=COR_TEXTO,
            selectbackground=COR_DESTAQUE,
            borderwidth=0,
            highlightthickness=0,
            font=("Consolas", 9),
        )
        self._lista_pastas.pack(side="left", fill="both", expand=True)
        for pasta in self._config["pastas_ignoradas"]:
            self._lista_pastas.insert("end", pasta)

        botoes_pastas = tk.Frame(corpo_pastas, bg=COR_FUNDO)
        botoes_pastas.pack(side="left", padx=(8, 0))

        tk.Button(
            botoes_pastas,
            text=self._t("adicionar"),
            width=14,
            command=self._adicionar_pasta,
            bg=COR_FUNDO_CARD,
            fg=COR_TEXTO,
            relief="flat",
            cursor="hand2",
        ).pack(pady=2)
        tk.Button(
            botoes_pastas,
            text=self._t("remover"),
            width=14,
            command=self._remover_pasta,
            bg=COR_FUNDO_CARD,
            fg=COR_TEXTO,
            relief="flat",
            cursor="hand2",
        ).pack(pady=2)
        tk.Button(
            botoes_pastas,
            text=self._t("restaurar_padrao"),
            width=14,
            command=self._restaurar_pastas,
            bg=COR_FUNDO_CARD,
            fg=COR_TEXTO_SECUNDARIO,
            relief="flat",
            cursor="hand2",
        ).pack(pady=2)

        secao_arquivos = tk.Frame(aba, bg=COR_FUNDO)
        secao_arquivos.pack(fill="x", padx=16, pady=(16, 8))

        tk.Label(
            secao_arquivos,
            text=self._t("arquivos_ignorados"),
            font=("Segoe UI", 10, "bold"),
            bg=COR_FUNDO,
            fg=COR_TEXTO,
        ).pack(anchor="w")
        tk.Label(
            secao_arquivos,
            text=self._t("arquivo_protegido_info", arquivo=ARQUIVO_PROTEGIDO),
            font=("Segoe UI", 9),
            bg=COR_FUNDO,
            fg=COR_TEXTO_SECUNDARIO,
        ).pack(anchor="w", pady=(2, 0))

        corpo_arquivos = tk.Frame(secao_arquivos, bg=COR_FUNDO)
        corpo_arquivos.pack(fill="x", pady=(6, 0))

        self._lista_arquivos = tk.Listbox(
            corpo_arquivos,
            height=5,
            bg=COR_FUNDO_CARD,
            fg=COR_TEXTO,
            selectbackground=COR_DESTAQUE,
            borderwidth=0,
            highlightthickness=0,
            font=("Consolas", 9),
        )
        self._lista_arquivos.pack(side="left", fill="both", expand=True)
        for nome in self._config["arquivos_ignorados"]:
            self._lista_arquivos.insert("end", nome)

        botoes_arquivos = tk.Frame(corpo_arquivos, bg=COR_FUNDO)
        botoes_arquivos.pack(side="left", padx=(8, 0))

        tk.Button(
            botoes_arquivos,
            text=self._t("adicionar"),
            width=14,
            command=self._adicionar_arquivo,
            bg=COR_FUNDO_CARD,
            fg=COR_TEXTO,
            relief="flat",
            cursor="hand2",
        ).pack(pady=2)
        tk.Button(
            botoes_arquivos,
            text=self._t("remover"),
            width=14,
            command=self._remover_arquivo,
            bg=COR_FUNDO_CARD,
            fg=COR_TEXTO,
            relief="flat",
            cursor="hand2",
        ).pack(pady=2)

    def _adicionar_pasta(self) -> None:
        valor = simpledialog.askstring(
            self._t("adicionar_pasta_ignorada"),
            self._t("nome_pasta"),
            parent=self,
        )
        if not valor:
            return
        valor = valor.strip()
        if valor and valor not in self._config["pastas_ignoradas"]:
            self._config["pastas_ignoradas"].append(valor)
            self._lista_pastas.insert("end", valor)

    def _remover_pasta(self) -> None:
        selecao = self._lista_pastas.curselection()
        if not selecao:
            return
        indice = selecao[0]
        valor = self._lista_pastas.get(indice)
        self._lista_pastas.delete(indice)
        if valor in self._config["pastas_ignoradas"]:
            self._config["pastas_ignoradas"].remove(valor)

    def _restaurar_pastas(self) -> None:
        padrao = restaurar_pastas_ignoradas_padrao()
        self._config["pastas_ignoradas"] = list(padrao)
        self._lista_pastas.delete(0, "end")
        for pasta in padrao:
            self._lista_pastas.insert("end", pasta)

    def _adicionar_arquivo(self) -> None:
        valor = simpledialog.askstring(
            self._t("adicionar_arquivo_ignorado"),
            self._t("nome_arquivo"),
            parent=self,
        )
        if not valor:
            return
        valor = valor.strip()
        if valor and valor not in self._config["arquivos_ignorados"]:
            self._config["arquivos_ignorados"].append(valor)
            self._lista_arquivos.insert("end", valor)

    def _remover_arquivo(self) -> None:
        selecao = self._lista_arquivos.curselection()
        if not selecao:
            return
        indice = selecao[0]
        valor = self._lista_arquivos.get(indice)

        if valor == ARQUIVO_PROTEGIDO:
            messagebox.showwarning(
                self._t("nao_permitido"),
                self._t("arquivo_protegido_erro", arquivo=ARQUIVO_PROTEGIDO),
                parent=self,
            )
            return

        self._lista_arquivos.delete(indice)
        if valor in self._config["arquivos_ignorados"]:
            self._config["arquivos_ignorados"].remove(valor)

    # ---------------- Idioma ----------------

    def _montar_aba_idioma(self, aba: tk.Frame) -> None:
        container = tk.Frame(aba, bg=COR_FUNDO)
        container.pack(fill="x", padx=20, pady=20)

        tk.Label(
            container,
            text=self._t("idioma_interface"),
            font=("Segoe UI", 11, "bold"),
            bg=COR_FUNDO,
            fg=COR_TEXTO,
        ).pack(anchor="w", pady=(0, 10))

        for codigo in ("pt_BR", "en"):
            tk.Radiobutton(
                container,
                text=NOMES_IDIOMAS[codigo],
                variable=self._idioma,
                value=codigo,
                bg=COR_FUNDO,
                fg=COR_TEXTO,
                selectcolor=COR_FUNDO_CARD,
                activebackground=COR_FUNDO,
                activeforeground=COR_TEXTO,
                font=("Segoe UI", 10),
                cursor="hand2",
            ).pack(anchor="w", pady=4)

        tk.Label(
            container,
            text=self._t("idioma_info"),
            font=("Segoe UI", 9),
            bg=COR_FUNDO,
            fg=COR_TEXTO_SECUNDARIO,
            justify="left",
            wraplength=500,
        ).pack(anchor="w", pady=(14, 0))

    # ---------------- Fechamento ----------------

    def _fechar(self) -> None:
        if ARQUIVO_PROTEGIDO not in self._config["arquivos_ignorados"]:
            self._config["arquivos_ignorados"].append(ARQUIVO_PROTEGIDO)
        self._config["idioma"] = self._idioma.get()
        self._on_salvar(self._config)
        self.destroy()
