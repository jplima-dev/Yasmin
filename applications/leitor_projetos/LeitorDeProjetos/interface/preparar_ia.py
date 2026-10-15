"""Opções e prévia do contexto para IA; leitura e exportação fora da UI."""
from __future__ import annotations

import queue
import threading
from functools import partial
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from configuracao.idiomas import IDIOMA_PADRAO, traduzir
from interface.dialogos import COR_FUNDO, COR_TEXTO, COR_FUNDO_CAMPO, COR_DESTAQUE
from processadores import ia


class JanelaPrepararIA(tk.Toplevel):
    def __init__(self, parent, projeto, destino, config, selecionados, on_concluir):
        super().__init__(parent)
        self._idioma = config.get("idioma", IDIOMA_PADRAO)
        self._config = config
        self._projeto, self._destino = projeto, destino
        self._selecionados = None if selecionados is None else list(selecionados)
        self._on_concluir = on_concluir
        self._plano = None
        self._ocupado = False
        self._fila = queue.Queue()
        self._after = None
        self.title(self._t("modo_preparar_ia"))
        self.configure(bg=COR_FUNDO)
        self.geometry("760x610")
        self.minsize(680, 520)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._fechar)

        self._limite = tk.StringVar(value=str(config.get("ia_limite_tokens", 30000)))
        self._formato = tk.StringVar(value=config.get("ia_formato", "Markdown"))
        self._arvore = tk.BooleanVar(value=config.get("ia_incluir_arvore", True))
        self._dividir = tk.BooleanVar(value=config.get("ia_dividir", True))
        corpo = tk.Frame(self, bg=COR_FUNDO)
        corpo.pack(fill="both", expand=True, padx=24, pady=20)
        linha = tk.Frame(corpo, bg=COR_FUNDO)
        linha.pack(fill="x")
        tk.Label(linha, text=self._t("ia_limite"), bg=COR_FUNDO, fg=COR_TEXTO).pack(side="left")
        limite = ttk.Entry(linha, textvariable=self._limite, width=12)
        limite.pack(side="left", padx=(8, 24))
        tk.Label(linha, text=self._t("ia_formato"), bg=COR_FUNDO, fg=COR_TEXTO).pack(side="left")
        formato = ttk.Combobox(linha, textvariable=self._formato, values=("Markdown", "TXT"),
                               state="readonly", width=12)
        formato.pack(side="left", padx=8)
        self._controles = [(limite, "normal"), (formato, "readonly")]
        for chave, variavel in (("ia_incluir_arvore", self._arvore), ("ia_dividir", self._dividir)):
            controle = tk.Checkbutton(corpo, text=self._t(chave), variable=variavel,
                                      bg=COR_FUNDO, fg=COR_TEXTO, selectcolor=COR_FUNDO_CAMPO,
                                      activebackground=COR_FUNDO, activeforeground=COR_TEXTO)
            controle.pack(anchor="w", pady=(8, 0))
            self._controles.append((controle, "normal"))
        tk.Label(corpo, text=self._t("ia_estimativa_nota"), wraplength=680, justify="left",
                 bg=COR_FUNDO, fg=COR_TEXTO).pack(fill="x", pady=12)

        self._resumo = tk.Label(corpo, text=self._t("ia_previa_pendente"), justify="left",
                                bg=COR_FUNDO, fg=COR_TEXTO, anchor="w")
        self._resumo.pack(fill="x", pady=(0, 10))
        tabela = tk.Frame(corpo, bg=COR_FUNDO)
        tabela.pack(fill="both", expand=True)
        self._partes = ttk.Treeview(tabela, columns=("nome", "tokens"), show="headings", height=6)
        self._partes.heading("nome", text=self._t("ia_parte"))
        self._partes.heading("tokens", text=self._t("ia_tokens"))
        self._partes.column("nome", width=450)
        self._partes.column("tokens", width=120, anchor="e")
        scroll = ttk.Scrollbar(tabela, orient="vertical", command=self._partes.yview)
        self._partes.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._partes.pack(fill="both", expand=True)
        self._avisos = ScrolledText(corpo, height=4, wrap="word", bg=COR_FUNDO_CAMPO,
                                    fg=COR_TEXTO, relief="flat", state="disabled")
        self._avisos.pack(fill="x", pady=10)
        botoes = tk.Frame(corpo, bg=COR_FUNDO)
        botoes.pack(fill="x")
        self._botao_previa = tk.Button(botoes, text=self._t("ia_calcular"), command=self._calcular)
        self._botao_previa.pack(side="left")
        self._botao_salvar = tk.Button(botoes, text=self._t("gerar_arquivos"), command=self._salvar,
                                       bg=COR_DESTAQUE, fg="white", state="disabled")
        self._botao_salvar.pack(side="right")
        self._traces = [(var, var.trace_add("write", self._invalidar))
                        for var in (self._limite, self._formato, self._arvore, self._dividir)]
        self._after = self.after_idle(self._calcular)

    def _t(self, chave, **valores):
        return traduzir(chave, self._idioma, **valores)

    def _numero(self, valor):
        texto = f"{valor:,}"
        return texto.replace(",", ".") if self._idioma == "pt_BR" else texto

    def _invalidar(self, *_):
        self._plano = None
        self._botao_salvar.config(state="disabled")
        self._partes.delete(*self._partes.get_children())
        self._resumo.config(text=self._t("ia_previa_pendente"))
        self._mostrar_avisos("")

    def _mostrar_avisos(self, texto):
        self._avisos.config(state="normal")
        self._avisos.delete("1.0", "end")
        self._avisos.insert("end", texto)
        self._avisos.config(state="disabled")

    def _trabalhar(self, tarefa, tipo):
        self._ocupado = True
        for controle, _ in self._controles:
            controle.config(state="disabled")
        self._botao_previa.config(state="disabled")
        self._botao_salvar.config(state="disabled")
        self._resumo.config(text=self._t("processando_projeto"))

        fila = self._fila

        def worker():
            try:
                fila.put((tipo, tarefa()))
            except Exception as exc:
                fila.put(("erro", str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self._after = self.after(80, self._checar)

    def _calcular(self):
        self._after = None
        if self._ocupado:
            return
        try:
            # Aceita também o limite digitado como 30.000 ou 30,000.
            limite = int(self._limite.get().replace(".", "").replace(",", "").replace(" ", ""))
            opcoes = ia.OpcoesIA(limite, self._formato.get(), self._arvore.get(), self._dividir.get())
        except ValueError:
            messagebox.showerror(self._t("modo_preparar_ia"), self._t("ia_limite_invalido"), parent=self)
            return
        self._invalidar()
        # O worker recebe só dados; não mantém referências a widgets Tk.
        self._trabalhar(partial(ia.preparar,
            self._projeto, tuple(self._config["extensoes_separado"]),
            list(self._config["pastas_ignoradas"]), list(self._config["arquivos_ignorados"]),
            opcoes, self._selecionados, self._idioma), "plano")

    def _checar(self):
        self._after = None
        try:
            tipo, dados = self._fila.get_nowait()
        except queue.Empty:
            self._after = self.after(80, self._checar)
            return
        self._ocupado = False
        for controle, estado in self._controles:
            controle.config(state=estado)
        self._botao_previa.config(state="normal")
        if tipo == "erro":
            self._resumo.config(text=self._t("ia_previa_pendente"))
            self._botao_salvar.config(state="normal" if self._plano and self._plano.partes else "disabled")
            messagebox.showerror(self._t("erro_processamento"), self._t(dados), parent=self)
        elif tipo == "plano":
            self._plano = dados
            self._resumo.config(text=self._t(
                "ia_resumo", arquivos=self._numero(dados.selecionados),
                caracteres=self._numero(dados.caracteres), tokens=self._numero(dados.tokens)))
            for parte in dados.partes:
                self._partes.insert("", "end", values=(parte.nome, "~" + self._numero(parte.tokens)))
            avisos = [self._t("ia_sensiveis", quantidade=dados.sensiveis_ignorados)]
            if dados.arquivos_divididos:
                avisos.append(self._t("ia_divididos", arquivos=", ".join(dados.arquivos_divididos)))
            if any(p.tokens > dados.opcoes.limite_tokens for p in dados.partes):
                avisos.append(self._t("ia_acima_limite"))
            if not dados.partes:
                avisos.append(self._t("ia_sem_arquivos"))
            avisos.extend(dados.erros)
            self._mostrar_avisos("\n".join(avisos))
            self._botao_salvar.config(state="normal" if dados.partes else "disabled")
        else:
            self.destroy()
            self._on_concluir(dados)

    def _salvar(self):
        if self._ocupado or self._plano is None or not self._plano.partes:
            return
        plano = self._plano
        self._config.update(ia_limite_tokens=plano.opcoes.limite_tokens,
                            ia_formato=plano.opcoes.formato,
                            ia_incluir_arvore=plano.opcoes.incluir_arvore,
                            ia_dividir=plano.opcoes.dividir)
        self._trabalhar(partial(ia.exportar, plano, self._destino), "salvo")

    def _fechar(self):
        if self._ocupado:
            return
        self.destroy()

    def destroy(self):
        if self._after is not None:
            self.after_cancel(self._after)
            self._after = None
        for var, identificador in self._traces:
            var.trace_remove("write", identificador)
        self._traces.clear()
        super().destroy()
