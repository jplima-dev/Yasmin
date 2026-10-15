"""
Diálogos modais reutilizáveis: pré-visualização de arquivos,
confirmação de segurança antes do processamento, ajuda/sobre, e
consulta ao histórico.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from configuracao.historico import carregar_historico, limpar_historico
from configuracao.idiomas import IDIOMA_PADRAO, traduzir
from interface.pre_visualizacao import JanelaPreVisualizacao

VERSAO = "1.0.4"

from interface.estilo import (
    COR_FUNDO, COR_FUNDO_CARD, COR_FUNDO_CAMPO, COR_TEXTO, COR_TEXTO_SECUNDARIO, COR_SUCESSO, COR_ERRO, COR_DESTAQUE, COR_DESTAQUE_HOVER,
)


def _centralizar_janela(janela: tk.Toplevel, largura: int, altura: int) -> None:
    janela.update_idletasks()
    tela_largura = janela.winfo_screenwidth()
    tela_altura = janela.winfo_screenheight()
    x = (tela_largura // 2) - (largura // 2)
    y = (tela_altura // 2) - (altura // 2)
    janela.geometry(f"{largura}x{altura}+{x}+{y}")


class JanelaConfirmacaoSeguranca(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        total_processar: int,
        total_sensiveis_ignorados: int,
        on_confirmar: Callable[[], None],
        idioma: str = IDIOMA_PADRAO,
    ):
        super().__init__(parent)
        self._idioma = idioma
        self.title(traduzir("confirmar_processamento", idioma))
        self.configure(bg=COR_FUNDO)
        self.transient(parent)
        self.resizable(False, False)
        _centralizar_janela(self, 400, 220)

        self._on_confirmar = on_confirmar

        corpo = tk.Frame(self, bg=COR_FUNDO)
        corpo.pack(fill="both", expand=True, padx=24, pady=24)

        tk.Label(
            corpo,
            text=traduzir("serao_processados", idioma, total=total_processar),
            font=("Segoe UI", 11),
            bg=COR_FUNDO,
            fg=COR_TEXTO,
        ).pack(anchor="w", pady=(0, 6))

        if total_sensiveis_ignorados > 0:
            tk.Label(
                corpo,
                text=traduzir("sensiveis_ignorados", idioma, total=total_sensiveis_ignorados),
                font=("Segoe UI", 10),
                bg=COR_FUNDO,
                fg=COR_ERRO,
            ).pack(anchor="w", pady=(0, 16))
        else:
            tk.Label(
                corpo,
                text=traduzir("nenhum_sensivel", idioma),
                font=("Segoe UI", 10),
                bg=COR_FUNDO,
                fg=COR_TEXTO_SECUNDARIO,
            ).pack(anchor="w", pady=(0, 16))

        tk.Label(
            corpo,
            text=traduzir("deseja_continuar", idioma),
            font=("Segoe UI", 11, "bold"),
            bg=COR_FUNDO,
            fg=COR_TEXTO,
        ).pack(anchor="w", pady=(0, 16))

        botoes = tk.Frame(corpo, bg=COR_FUNDO)
        botoes.pack(fill="x")

        tk.Button(
            botoes,
            text=traduzir("cancelar", idioma),
            command=self.destroy,
            bg=COR_FUNDO_CARD,
            fg=COR_TEXTO,
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
        ).pack(side="right", padx=(8, 0))

        tk.Button(
            botoes,
            text=traduzir("continuar", idioma),
            command=self._confirmar,
            bg=COR_DESTAQUE,
            fg="#ffffff",
            activebackground=COR_DESTAQUE_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")

    def _confirmar(self) -> None:
        self.destroy()
        self._on_confirmar()


class JanelaAjuda(tk.Toplevel):
    def __init__(self, parent: tk.Widget, idioma: str = IDIOMA_PADRAO):
        super().__init__(parent)
        self.title(traduzir("sobre_ajuda", idioma))
        self.configure(bg=COR_FUNDO)
        self.transient(parent)
        _centralizar_janela(self, 520, 480)

        container = tk.Frame(self, bg=COR_FUNDO)
        container.pack(fill="both", expand=True, padx=24, pady=20)

        texto = tk.Text(
            container,
            bg=COR_FUNDO,
            fg=COR_TEXTO,
            font=("Segoe UI", 10),
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
        )
        texto.pack(fill="both", expand=True)
        texto.tag_config("titulo", font=("Segoe UI", 11, "bold"), foreground=COR_DESTAQUE)

        conteudo = [
            ("titulo", traduzir("ajuda_cabecalho", idioma, versao=VERSAO)),
            (None, traduzir("ajuda_windows", idioma)),
            ("titulo", traduzir("ajuda_para_que_serve_titulo", idioma)),
            (None, traduzir("ajuda_para_que_serve", idioma)),
            ("titulo", traduzir("ajuda_modos_titulo", idioma)),
            (None, traduzir("ajuda_modos", idioma)),
            ("titulo", traduzir("ajuda_selecionar_titulo", idioma)),
            (None, traduzir("ajuda_selecionar", idioma)),
            ("titulo", traduzir("ajuda_extensoes_titulo", idioma)),
            (None, traduzir("ajuda_extensoes", idioma)),
            ("titulo", traduzir("ajuda_ignorados_titulo", idioma)),
            (None, traduzir("ajuda_ignorados", idioma)),
            ("titulo", traduzir("ajuda_env_titulo", idioma)),
            (None, traduzir("ajuda_env", idioma)),
            ("titulo", traduzir("ajuda_saida_titulo", idioma)),
            (None, traduzir("ajuda_saida", idioma)),
        ]

        for tag, trecho in conteudo:
            if tag:
                texto.insert("end", trecho, tag)
            else:
                texto.insert("end", trecho)

        texto.config(state="disabled")

        tk.Button(
            self,
            text=traduzir("fechar", idioma),
            command=self.destroy,
            bg=COR_FUNDO_CARD,
            fg=COR_TEXTO,
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
        ).pack(pady=(0, 16))


class JanelaHistorico(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        on_limpar: Optional[Callable[[], None]] = None,
        idioma: str = IDIOMA_PADRAO,
    ):
        super().__init__(parent)
        self._idioma = idioma
        self.title(traduzir("historico", idioma))
        self.configure(bg=COR_FUNDO)
        self.transient(parent)
        _centralizar_janela(self, 520, 440)

        self._on_limpar = on_limpar

        container = tk.Frame(self, bg=COR_FUNDO)
        container.pack(fill="both", expand=True, padx=20, pady=(16, 8))

        entradas = carregar_historico()

        if not entradas:
            tk.Label(
                container,
                text=traduzir("nenhum_processamento", idioma),
                font=("Segoe UI", 10),
                bg=COR_FUNDO,
                fg=COR_TEXTO_SECUNDARIO,
            ).pack(pady=40)
        else:
            scrollbar = ttk.Scrollbar(container)
            scrollbar.pack(side="right", fill="y")

            lista = tk.Text(
                container,
                bg=COR_FUNDO_CARD,
                fg=COR_TEXTO,
                font=("Consolas", 9),
                wrap="none",
                yscrollcommand=scrollbar.set,
                borderwidth=0,
                highlightthickness=0,
            )
            lista.pack(fill="both", expand=True)
            scrollbar.config(command=lista.yview)

            for entrada in entradas:
                chave_modo = {"separado": "modo_arquivo_unico", "junto": "modo_arquivos_separados",
                              "ia": "modo_preparar_ia"}.get(entrada.modo, "modo_arquivo_unico")
                modo_label = traduzir(chave_modo, idioma)
                linha = traduzir(
                    "historico_linha",
                    idioma,
                    data=entrada.data,
                    projeto=entrada.nome_projeto,
                    quantidade=entrada.quantidade_arquivos,
                    modo=modo_label,
                )
                lista.insert("end", linha)

            lista.config(state="disabled")

        rodape = tk.Frame(self, bg=COR_FUNDO)
        rodape.pack(fill="x", padx=20, pady=(8, 16))

        if entradas:
            tk.Button(
                rodape,
                text=traduzir("limpar_historico", idioma),
                command=self._limpar,
                bg=COR_FUNDO_CARD,
                fg=COR_ERRO,
                relief="flat",
                padx=16,
                pady=6,
                cursor="hand2",
            ).pack(side="left")

        tk.Button(
            rodape,
            text=traduzir("fechar", idioma),
            command=self.destroy,
            bg=COR_FUNDO_CARD,
            fg=COR_TEXTO,
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
        ).pack(side="right")

    def _limpar(self) -> None:
        limpar_historico()
        if self._on_limpar:
            self._on_limpar()
        self.destroy()
