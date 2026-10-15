"""Prévia única para incluir ou ignorar vários arquivos e pastas."""
from __future__ import annotations

from pathlib import PurePosixPath
import tkinter as tk
from tkinter import ttk

from configuracao.idiomas import IDIOMA_PADRAO, traduzir
from interface.estilo import (
    COR_FUNDO, COR_FUNDO_CARD, COR_FUNDO_CAMPO, COR_TEXTO, COR_TEXTO_SECUNDARIO,
    COR_DESTAQUE, COR_DESTAQUE_HOVER, COR_AVISO, configurar_tema,
)
from utils.selecao import SelecaoProjeto


class JanelaPreVisualizacao(tk.Toplevel):
    def __init__(self, parent, raiz_projeto, extensoes, pastas_ignoradas, arquivos_ignorados,
                 selecionados=None, on_confirmar=None, idioma=IDIOMA_PADRAO):
        super().__init__(parent)
        configurar_tema(self)
        self._idioma = idioma
        self._on_confirmar = on_confirmar
        self._modelo = SelecaoProjeto(raiz_projeto, extensoes, pastas_ignoradas,
                                      arquivos_ignorados, selecionados)
        self.title(self._t("pre_visualizacao"))
        self.configure(bg=COR_FUNDO)
        self.geometry("920x680")
        self.minsize(780, 560)
        self.transient(parent)
        self.grab_set()

        cabecalho = tk.Frame(self, bg=COR_FUNDO)
        cabecalho.pack(fill="x", padx=28, pady=(24, 12))
        tk.Label(cabecalho, text=self._t("pre_visualizar_arquivos"), bg=COR_FUNDO, fg=COR_TEXTO,
                 font=("Segoe UI Variable Display", 20, "bold")).pack(anchor="w")
        tk.Label(cabecalho, text=self._t("previa_instrucoes"), bg=COR_FUNDO, fg=COR_TEXTO_SECUNDARIO,
                 wraplength=720, justify="left", font=("Segoe UI", 10)).pack(anchor="w", pady=(6, 0))
        acoes = tk.Frame(cabecalho, bg=COR_FUNDO)
        acoes.pack(fill="x", pady=(16, 0))
        self._botao_ignorar = self._botao(acoes, "previa_ignorar_selecionados", self._ignorar)
        self._botao_incluir = self._botao(acoes, "previa_incluir_selecionados", self._incluir)
        for botao in (self._botao_ignorar, self._botao_incluir):
            botao.pack(side="left", padx=(0, 8))
        self._botao(acoes, "previa_selecionar_todos", self._selecionar_todos).pack(side="right")

        # Reserva o rodapé antes da árvore para manter os botões visíveis.
        rodape = tk.Frame(self, bg=COR_FUNDO)
        rodape.pack(side="bottom", fill="x", padx=28, pady=(16, 24))
        self._botao(rodape, "confirmar_selecao", self._confirmar, destaque=True).pack(side="right")
        self._botao(rodape, "cancelar", self.destroy).pack(side="right", padx=8)
        self._resumo = tk.Label(self, bg=COR_FUNDO, fg=COR_TEXTO_SECUNDARIO,
                                anchor="w", justify="left", font=("Segoe UI", 9), wraplength=720)
        self._resumo.pack(side="bottom", fill="x", padx=28, pady=(6, 0))

        container = tk.Frame(self, bg=COR_FUNDO_CARD, highlightthickness=1, highlightbackground="#20314d")
        container.pack(fill="both", expand=True, padx=28, pady=8)
        self._arvore = ttk.Treeview(container, columns=("incluir", "tipo", "estado"),
                                    selectmode="extended", style="Leitor.Treeview")
        self._arvore.heading("#0", text=self._t("nome_ou_caminho"))
        self._arvore.heading("incluir", text=self._t("previa_incluir"))
        self._arvore.heading("tipo", text=self._t("tipo"))
        self._arvore.heading("estado", text=self._t("previa_estado"))
        self._arvore.column("#0", width=340, minwidth=200)
        self._arvore.column("incluir", width=70, minwidth=70, stretch=False, anchor="center")
        self._arvore.column("tipo", width=80, minwidth=60, stretch=False)
        self._arvore.column("estado", width=200, minwidth=150, stretch=False)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self._arvore.yview,
                                  style="Leitor.Vertical.TScrollbar")
        self._arvore.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        horizontal = ttk.Scrollbar(container, orient="horizontal", command=self._arvore.xview,
                                   style="Leitor.Horizontal.TScrollbar")
        self._arvore.configure(xscrollcommand=horizontal.set)
        horizontal.pack(side="bottom", fill="x")
        self._arvore.pack(fill="both", expand=True)
        self._arvore.tag_configure("previa_ignorado", foreground=COR_AVISO)
        self._arvore.tag_configure("previa_bloqueado", foreground=COR_TEXTO_SECUNDARIO)
        self._arvore.bind("<Control-a>", self._selecionar_todos)
        self._arvore.bind("<Button-1>", self._clicar_inclusao)
        self._arvore.bind("<<TreeviewSelect>>", self._atualizar_acoes)
        self._arvore.bind("<space>", self._alternar_selecao)
        self._atualizar_arvore()

    def _botao(self, parent, chave, comando, destaque=False):
        return tk.Button(parent, text=self._t(chave), command=comando, relief="flat", bd=0,
                         bg=COR_DESTAQUE if destaque else COR_FUNDO_CAMPO, fg=COR_TEXTO,
                         activebackground=COR_DESTAQUE_HOVER if destaque else "#244573",
                         activeforeground=COR_TEXTO, disabledforeground="#60738e", cursor="hand2",
                         font=("Segoe UI", 10, "bold" if destaque else "normal"), padx=14, pady=9)

    def _atualizar_acoes(self, evento=None):
        habilitado = any(self._modelo.itens[p].estado != "previa_bloqueado"
                        for p in self._arvore.selection() if p in self._modelo.itens)
        for botao in (self._botao_incluir, self._botao_ignorar):
            botao.config(state="normal" if habilitado else "disabled")

    def _clicar_inclusao(self, evento):
        if self._arvore.identify_region(evento.x, evento.y) != "cell":
            return
        if self._arvore.identify_column(evento.x) != "#1":
            return
        caminho = self._arvore.identify_row(evento.y)
        if caminho:
            self._arvore.selection_set(caminho)
            self._alternar_selecao()
        return "break"

    def _alternar_selecao(self, evento=None):
        caminhos = list(self._arvore.selection())
        if not caminhos:
            return "break"
        if all(self._modelo.itens[p].estado in ("previa_ignorado", "previa_nao_selecionado", "previa_bloqueado")
               for p in caminhos):
            self._incluir()
        else:
            self._ignorar()
        return "break"

    def _t(self, chave, **valores):
        return traduzir(chave, self._idioma, **valores)

    def _atualizar_arvore(self):
        selecionados = self._arvore.selection()
        abertos = {c for c in self._modelo.itens if self._arvore.exists(c) and self._arvore.item(c, "open")}
        posicao = self._arvore.yview()[0]
        primeira = not self._arvore.get_children()
        self._arvore.delete(*self._arvore.get_children())
        for caminho, item in self._modelo.itens.items():
            relativo = PurePosixPath(caminho)
            pai = "" if str(relativo.parent) == "." else str(relativo.parent)
            marcado = "☑" if item.estado in ("previa_pasta", "previa_incluido") else "☐"
            if item.estado == "previa_bloqueado":
                marcado = "—"
            self._arvore.insert(pai, "end", iid=caminho, text=relativo.name,
                                values=(marcado, self._t("pasta" if item.pasta else "arquivo"), self._t(item.estado)),
                                tags=(item.estado,), open=caminho in abertos or primeira and pai == "")
        self._arvore.selection_set([p for p in selecionados if self._arvore.exists(p)])
        self._arvore.yview_moveto(posicao)
        incluidos, ignorados = self._modelo.resultado()
        texto = self._t("previa_resumo", incluidos=len(incluidos), ignorados=len(ignorados))
        if self._modelo.erros:
            texto += "\n" + self._t("previa_erros", quantidade=len(self._modelo.erros))
        self._resumo.config(text=texto)
        self._atualizar_acoes()

    def _ignorar(self):
        self._modelo.ignorar(self._arvore.selection())
        self._atualizar_arvore()

    def _incluir(self):
        self._modelo.incluir(self._arvore.selection())
        self._atualizar_arvore()

    def _selecionar_todos(self, evento=None):
        self._arvore.selection_set(list(self._modelo.itens))
        return "break"

    def _confirmar(self):
        if self._on_confirmar:
            incluidos, ignorados = self._modelo.resultado()
            self._on_confirmar(incluidos, ignorados, self._modelo.pastas_ignoradas,
                               self._modelo.arquivos_ignorados)
        self.destroy()
