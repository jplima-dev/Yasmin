"""
Janela principal do Leitor de Projetos.

Responsável apenas por orquestração de UI: delega toda a lógica de
processamento para processadores/separado.py e processadores/junto.py,
e toda a persistência para configuracao/config.py e
configuracao/historico.py.
"""

from __future__ import annotations

import datetime
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from configuracao.config import carregar_config, salvar_config
from configuracao.historico import adicionar_entrada
from configuracao.idiomas import IDIOMA_PADRAO, IDIOMAS_SUPORTADOS, traduzir
from interface.configuracoes import JanelaConfiguracoes
from interface.dialogos import (
    JanelaAjuda,
    JanelaConfirmacaoSeguranca,
    JanelaHistorico,
    JanelaPreVisualizacao,
)
from interface.preparar_ia import JanelaPrepararIA
from processadores import ia, junto, separado
from utils.arquivos import obter_pasta_saida_padrao

# Paleta com contraste alto e aparência próxima aos aplicativos atuais do Windows.
from interface.estilo import (
    COR_FUNDO, COR_FUNDO_CARD, COR_FUNDO_CAMPO, COR_TEXTO, COR_TEXTO_SECUNDARIO, COR_SUCESSO, COR_ERRO, COR_AVISO, COR_DESTAQUE, COR_DESTAQUE_HOVER,
)

MODO_ARQUIVO_UNICO = "separado"
MODO_ARQUIVOS_SEPARADOS = "junto"
MODO_PREPARAR_IA = "ia"
VERSAO = "1.0.4"

CHAVE_DESCRICAO_MODO = {
    MODO_PREPARAR_IA: "descricao_preparar_ia",
    MODO_ARQUIVO_UNICO: "descricao_arquivo_unico",
    MODO_ARQUIVOS_SEPARADOS: "descricao_arquivos_separados",
}

CHAVE_NOME_MODO = {
    MODO_PREPARAR_IA: "modo_preparar_ia",
    MODO_ARQUIVO_UNICO: "modo_arquivo_unico",
    MODO_ARQUIVOS_SEPARADOS: "modo_arquivos_separados",
}


class JanelaPrincipal(tk.Tk):
    def __init__(self):
        super().__init__()

        self.configure(bg=COR_FUNDO)
        self._fechando = False
        self._after_fila: str | None = None

        self._config = carregar_config()
        if self._config.get("idioma") not in IDIOMAS_SUPORTADOS:
            self._config["idioma"] = IDIOMA_PADRAO
        self.title(self._t("titulo_janela", versao=VERSAO))

        largura = self._config.get("janela_largura", 900)
        altura = self._config.get("janela_altura", 640)
        self.geometry(f"{largura}x{altura}")
        self.minsize(760, 560)

        self._pasta_projeto: str = self._config.get("ultima_pasta_projeto", "")
        self._pasta_saida: str = self._config.get("ultima_pasta_saida", "")
        self._modo = tk.StringVar(value=self._config.get("ultimo_modo", MODO_ARQUIVO_UNICO))

        self._fila_eventos: queue.Queue = queue.Queue()
        self._thread_processamento: threading.Thread | None = None
        self._ultimo_resultado = None

        self._montar_layout()
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        # ``zoomed`` maximiza a janela, mas preserva a moldura nativa do
        # Windows (minimizar, restaurar e fechar). É diferente de fullscreen.
        self.after_idle(self._maximizar)

        # Variáveis para armazenar seleção de arquivos feita na pré‑visualização
        self._arquivos_selecionados: list[str] | None = None
        self._arquivos_ignorados: list[str] | None = None

    def _t(self, chave: str, **valores: object) -> str:
        return traduzir(chave, self._config.get("idioma", IDIOMA_PADRAO), **valores)

    def _maximizar(self) -> None:
        if self._fechando:
            return
        try:
            self.state("zoomed")
        except tk.TclError:
            # Fallback útil caso a aplicação seja executada fora do Windows.
            self.attributes("-zoomed", True)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _montar_layout(self) -> None:
        topo = tk.Frame(self, bg=COR_FUNDO)
        topo.pack(fill="x", padx=40, pady=(28, 4))

        tk.Label(
            topo, text=self._t("titulo_app"),
            font=("Segoe UI Variable Display", 22, "bold"),
            bg=COR_FUNDO, fg=COR_TEXTO,
        ).pack(anchor="w")
        tk.Label(
            topo,
            text=self._t("descricao_app"),
            font=("Segoe UI", 10),
            bg=COR_FUNDO, fg=COR_TEXTO_SECUNDARIO,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        barra_acoes = tk.Frame(self, bg=COR_FUNDO)
        barra_acoes.pack(fill="x", padx=40, pady=(14, 0))

        for texto, comando in [
            (self._t("configuracoes"), self._abrir_configuracoes),
            (self._t("ajuda"), self._abrir_ajuda),
            (self._t("historico"), self._abrir_historico),
        ]:
            tk.Button(
                barra_acoes, text=texto, command=comando,
                bg=COR_FUNDO_CARD, fg=COR_TEXTO,
                activebackground=COR_FUNDO_CAMPO, activeforeground=COR_TEXTO,
                relief="flat", bd=0, padx=14, pady=7, cursor="hand2",
                font=("Segoe UI", 9),
            ).pack(side="left", padx=(0, 8))

        corpo = tk.Frame(self, bg=COR_FUNDO)
        corpo.pack(fill="both", expand=True, padx=40, pady=20)

        # O rodapé permanece acessível mesmo em janelas pequenas.
        self._montar_barra_inferior(corpo)
        self._montar_secao_progresso(corpo)
        rolagem = tk.Frame(corpo, bg=COR_FUNDO)
        rolagem.pack(fill="both", expand=True)
        canvas = tk.Canvas(rolagem, bg=COR_FUNDO, highlightthickness=0)
        scrollbar = ttk.Scrollbar(rolagem, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        conteudo = tk.Frame(canvas, bg=COR_FUNDO)
        item = canvas.create_window((0, 0), window=conteudo, anchor="nw")
        conteudo.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda evento: canvas.itemconfigure(item, width=evento.width))

        def rolar(evento):
            if evento.widget.winfo_toplevel() == self and conteudo.winfo_height() > canvas.winfo_height():
                canvas.yview_scroll(-1 if evento.delta > 0 else 1, "units")

        self.bind("<MouseWheel>", rolar)
        self._montar_secao_projeto(conteudo)
        self._montar_secao_modo(conteudo)
        self._montar_secao_saida(conteudo)

    def _card(self, parent: tk.Widget) -> tk.Frame:
        card = tk.Frame(
            parent, bg=COR_FUNDO_CARD,
            highlightthickness=1, highlightbackground="#20314d",
        )
        card.pack(fill="x", pady=(0, 14))
        return card

    def _montar_secao_projeto(self, parent: tk.Widget) -> None:
        card = self._card(parent)
        interno = tk.Frame(card, bg=COR_FUNDO_CARD)
        interno.pack(fill="x", padx=16, pady=12)

        tk.Label(
            interno, text=self._t("projeto_selecionado"),
            font=("Segoe UI", 10, "bold"),
            bg=COR_FUNDO_CARD, fg=COR_TEXTO,
        ).pack(anchor="w")

        linha = tk.Frame(interno, bg=COR_FUNDO_CARD)
        linha.pack(fill="x", pady=(8, 0))

        self._label_pasta_projeto = tk.Label(
            linha, text=self._texto_pasta_projeto(),
            font=("Segoe UI", 9),
            bg=COR_FUNDO_CAMPO, fg=COR_TEXTO,
            anchor="w", padx=10, pady=8,
        )
        self._label_pasta_projeto.pack(side="left", fill="x", expand=True)

        tk.Button(
            linha, text=self._t("selecionar_pasta"), command=self._selecionar_pasta_projeto,
            bg=COR_DESTAQUE, fg="#ffffff", activebackground=COR_DESTAQUE_HOVER,
            activeforeground="#ffffff", relief="flat", bd=0,
            padx=12, pady=6, cursor="hand2", font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            linha, text=self._t("abrir_pasta"), command=lambda: self._abrir_no_explorador(self._pasta_projeto),
            bg=COR_FUNDO_CAMPO, fg=COR_TEXTO_SECUNDARIO, relief="flat",
            padx=12, pady=6, cursor="hand2", font=("Segoe UI", 9),
        ).pack(side="left", padx=(8, 0))

        pre_viz = tk.Frame(interno, bg=COR_FUNDO_CARD)
        pre_viz.pack(fill="x", pady=(10, 0))

        tk.Button(
            pre_viz, text=self._t("pre_visualizar_arquivos"), command=self._pre_visualizar,
            bg=COR_FUNDO_CAMPO, fg=COR_TEXTO, relief="flat",
            padx=12, pady=6, cursor="hand2", font=("Segoe UI", 9),
        ).pack(side="left")

    def _texto_pasta_projeto(self) -> str:
        if self._pasta_projeto:
            return self._pasta_projeto
        return self._t("nenhuma_pasta_selecionada")

    def _montar_secao_modo(self, parent: tk.Widget) -> None:
        card = self._card(parent)
        interno = tk.Frame(card, bg=COR_FUNDO_CARD)
        interno.pack(fill="x", padx=16, pady=12)

        tk.Label(
            interno, text=self._t("modo_processamento"),
            font=("Segoe UI", 10, "bold"),
            bg=COR_FUNDO_CARD, fg=COR_TEXTO,
        ).pack(anchor="w")

        opcoes = tk.Frame(interno, bg=COR_FUNDO_CARD)
        opcoes.pack(fill="x", pady=(8, 0))

        for modo, chave_nome in CHAVE_NOME_MODO.items():
            nome = self._t(chave_nome)
            linha_opcao = tk.Frame(opcoes, bg=COR_FUNDO_CARD)
            linha_opcao.pack(fill="x", pady=2)

            tk.Radiobutton(
                linha_opcao, text=nome, variable=self._modo, value=modo,
                command=self._limpar_selecao,
                bg=COR_FUNDO_CARD, fg=COR_TEXTO, selectcolor=COR_FUNDO_CAMPO,
                activebackground=COR_FUNDO_CARD, activeforeground=COR_TEXTO,
                font=("Segoe UI", 10, "bold"), cursor="hand2",
            ).pack(anchor="w")

            tk.Label(
                linha_opcao, text=self._t(CHAVE_DESCRICAO_MODO[modo]),
                font=("Segoe UI", 9),
                bg=COR_FUNDO_CARD, fg=COR_TEXTO_SECUNDARIO,
            ).pack(anchor="w", padx=(24, 0))

    def _montar_secao_saida(self, parent: tk.Widget) -> None:
        card = self._card(parent)
        interno = tk.Frame(card, bg=COR_FUNDO_CARD)
        interno.pack(fill="x", padx=16, pady=12)

        tk.Label(
            interno, text=self._t("pasta_destino"),
            font=("Segoe UI", 10, "bold"),
            bg=COR_FUNDO_CARD, fg=COR_TEXTO,
        ).pack(anchor="w")

        linha = tk.Frame(interno, bg=COR_FUNDO_CARD)
        linha.pack(fill="x", pady=(8, 0))

        self._label_pasta_saida = tk.Label(
            linha, text=self._texto_pasta_saida(),
            font=("Segoe UI", 9),
            bg=COR_FUNDO_CAMPO, fg=COR_TEXTO,
            anchor="w", padx=10, pady=8,
        )
        self._label_pasta_saida.pack(side="left", fill="x", expand=True)

        # Renomeado para evitar duplicação de texto de botão "Selecionar pasta"
        tk.Button(
            linha, text=self._t("selecionar_pasta_saida"), command=self._selecionar_pasta_saida,
            bg=COR_FUNDO_CAMPO, fg=COR_TEXTO, relief="flat",
            padx=12, pady=6, cursor="hand2", font=("Segoe UI", 9),
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            linha, text=self._t("abrir_pasta"), command=lambda: self._abrir_no_explorador(self._pasta_saida_efetiva()),
            bg=COR_FUNDO_CAMPO, fg=COR_TEXTO_SECUNDARIO, relief="flat",
            padx=12, pady=6, cursor="hand2", font=("Segoe UI", 9),
        ).pack(side="left", padx=(8, 0))

    def _texto_pasta_saida(self) -> str:
        if self._pasta_saida:
            return self._pasta_saida
        return self._t("padrao_caminho", caminho=obter_pasta_saida_padrao())

    def _pasta_saida_efetiva(self) -> str:
        return self._pasta_saida or str(obter_pasta_saida_padrao())

    def _montar_secao_progresso(self, parent: tk.Widget) -> None:
        self._card_progresso = tk.Frame(parent, bg=COR_FUNDO_CARD)
        # Não empacotado inicialmente — só aparece durante o processamento.

        interno = tk.Frame(self._card_progresso, bg=COR_FUNDO_CARD)
        interno.pack(fill="x", padx=16, pady=12)

        self._label_status_progresso = tk.Label(
            interno, text=self._t("processando_projeto"),
            font=("Segoe UI", 10, "bold"),
            bg=COR_FUNDO_CARD, fg=COR_TEXTO,
        )
        self._label_status_progresso.pack(anchor="w")

        self._label_arquivo_atual = tk.Label(
            interno, text="", font=("Segoe UI", 9),
            bg=COR_FUNDO_CARD, fg=COR_TEXTO_SECUNDARIO,
        )
        self._label_arquivo_atual.pack(anchor="w", pady=(4, 8))

        self._barra_progresso = ttk.Progressbar(
            interno, orient="horizontal", mode="determinate",
        )
        self._barra_progresso.pack(fill="x")

        self._label_contador = tk.Label(
            interno, text="", font=("Segoe UI", 9),
            bg=COR_FUNDO_CARD, fg=COR_TEXTO_SECUNDARIO,
        )
        self._label_contador.pack(anchor="e", pady=(4, 0))

    def _montar_barra_inferior(self, parent: tk.Widget) -> None:
        self._barra_inferior = tk.Frame(parent, bg=COR_FUNDO)
        self._barra_inferior.pack(side="bottom", fill="x", pady=(8, 0))

        self._botao_gerar = tk.Button(
            self._barra_inferior, text=self._t("gerar_arquivos"),
            command=self._iniciar_fluxo_processamento,
            bg=COR_DESTAQUE, fg="#ffffff", activebackground=COR_DESTAQUE_HOVER,
            activeforeground="#ffffff", relief="flat", bd=0,
            padx=24, pady=10, cursor="hand2",
            font=("Segoe UI", 11, "bold"),
        )
        self._botao_gerar.pack(side="left")

        self._label_mensagem = tk.Label(
            self._barra_inferior, text="",
            font=("Segoe UI", 9),
            bg=COR_FUNDO, fg=COR_TEXTO_SECUNDARIO,
        )
        self._label_mensagem.pack(side="left", padx=(16, 0))

    # ------------------------------------------------------------------
    # Seleção de pastas
    # ------------------------------------------------------------------

    def _selecionar_pasta_projeto(self) -> None:
        pasta = filedialog.askdirectory(title=self._t("selecionar_pasta_projeto_titulo"))
        if not pasta:
            return
        self._pasta_projeto = pasta
        self._limpar_selecao()
        self._label_pasta_projeto.config(text=self._texto_pasta_projeto())
        self._persistir_config()

    def _selecionar_pasta_saida(self) -> None:
        pasta = filedialog.askdirectory(title=self._t("selecionar_pasta_destino_titulo"))
        if not pasta:
            return
        self._pasta_saida = pasta
        self._label_pasta_saida.config(text=self._texto_pasta_saida())
        self._persistir_config()

    def _abrir_no_explorador(self, caminho: str) -> None:
        if not caminho or not os.path.isdir(caminho):
            messagebox.showinfo(self._t("pasta_nao_encontrada"), self._t("selecione_pasta_valida"))
            return

        if sys.platform == "win32":
            os.startfile(caminho)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", caminho])
        else:
            subprocess.run(["xdg-open", caminho])

    # ------------------------------------------------------------------
    # Pré-visualização
    # ------------------------------------------------------------------

    def _pre_visualizar(self) -> None:
        """Abre a janela de pré‑visualização permitindo ao usuário escolher
        quais arquivos serão processados. A seleção é armazenada em
        ``self._arquivos_selecionados`` e ``self._arquivos_ignorados`` para ser
        utilizada posteriormente na fase de geração.
        """
        if self._focar_dialogo(JanelaPreVisualizacao):
            return
        if not self._validar_projeto_selecionado():
            return

        chave_extensoes = "extensoes_junto" if self._modo.get() == MODO_ARQUIVOS_SEPARADOS else "extensoes_separado"
        JanelaPreVisualizacao(
            self,
            self._pasta_projeto,
            self._config[chave_extensoes],
            self._config["pastas_ignoradas"],
            self._config["arquivos_ignorados"],
            selecionados=self._arquivos_selecionados,
            on_confirmar=self._atualizar_selecao,
            idioma=self._config.get("idioma", IDIOMA_PADRAO),
        )

    def _atualizar_selecao(self, selecionados: list[str], ignorados: list[str],
                          pastas_ignoradas: list[str], arquivos_ignorados: list[str]) -> None:
        """Callback usado pela janela de pré‑visualização para armazenar a
        escolha do usuário.
        """
        self._config["pastas_ignoradas"] = list(pastas_ignoradas)
        self._config["arquivos_ignorados"] = list(arquivos_ignorados)
        self._persistir_config()
        self._arquivos_selecionados = selecionados
        self._arquivos_ignorados = ignorados
        self._label_mensagem.config(text=self._t("previa_selecao_salva", quantidade=len(selecionados)))

    def _limpar_selecao(self) -> None:
        self._arquivos_selecionados = None
        self._arquivos_ignorados = None

    def _listar_arquivos_modo_atual(self) -> tuple[list[str], list[str]]:
        """Retorna as listas de arquivos a processar e a ignorar.
        Se o usuário já fez uma seleção na pré‑visualização, utiliza essa
        seleção; caso contrário, calcula a partir da configuração.
        """
        if self._arquivos_selecionados is not None and self._arquivos_ignorados is not None:
            return self._arquivos_selecionados, self._arquivos_ignorados

        modo = self._modo.get()
        if modo in (MODO_ARQUIVO_UNICO, MODO_PREPARAR_IA):
            extensoes = tuple(self._config["extensoes_separado"])
            processador = ia if modo == MODO_PREPARAR_IA else separado
            processaveis, ignorados, _ = processador.listar_arquivos_projeto(
                self._pasta_projeto, extensoes,
                self._config["pastas_ignoradas"], self._config["arquivos_ignorados"],
            )
        else:
            extensoes = tuple(self._config["extensoes_junto"])
            processaveis, ignorados, _ = junto.listar_arquivos_projeto(
                self._pasta_projeto, extensoes,
                self._config["pastas_ignoradas"], self._config["arquivos_ignorados"],
            )
        return processaveis, ignorados

    def _validar_projeto_selecionado(self) -> bool:
        if not self._pasta_projeto:
            messagebox.showwarning(self._t("nenhum_projeto_selecionado"), self._t("selecione_projeto_primeiro"))
            return False
        if not os.path.isdir(self._pasta_projeto):
            messagebox.showerror(self._t("pasta_invalida"), self._t("pasta_projeto_nao_existe"))
            return False
        return True

    # ------------------------------------------------------------------
    # Fluxo de processamento
    # ------------------------------------------------------------------

    def _iniciar_fluxo_processamento(self) -> None:
        if not self._validar_projeto_selecionado():
            return

        if self._thread_processamento and self._thread_processamento.is_alive():
            messagebox.showinfo(self._t("em_andamento"), self._t("processamento_em_execucao"))
            return

        if self._modo.get() == MODO_PREPARAR_IA:
            if self._focar_dialogo(JanelaPrepararIA):
                return
            JanelaPrepararIA(
                self, self._pasta_projeto, self._pasta_saida_efetiva(), self._config,
                self._arquivos_selecionados, self._finalizar_processamento,
            )
            return

        if self._focar_dialogo(JanelaConfirmacaoSeguranca):
            return
        processaveis, ignorados = self._listar_arquivos_modo_atual()
        _, _, sensiveis = self._listar_com_contagem_sensiveis()

        JanelaConfirmacaoSeguranca(
            self,
            total_processar=len(processaveis),
            total_sensiveis_ignorados=sensiveis,
            on_confirmar=self._executar_processamento,
            idioma=self._config.get("idioma", IDIOMA_PADRAO),
        )

    def _listar_com_contagem_sensiveis(self) -> tuple[list[str], list[str], int]:
        modo = self._modo.get()
        if modo == MODO_ARQUIVO_UNICO:
            extensoes = tuple(self._config["extensoes_separado"])
            return separado.listar_arquivos_projeto(
                self._pasta_projeto, extensoes,
                self._config["pastas_ignoradas"], self._config["arquivos_ignorados"],
            )
        extensoes = tuple(self._config["extensoes_junto"])
        return junto.listar_arquivos_projeto(
            self._pasta_projeto, extensoes,
            self._config["pastas_ignoradas"], self._config["arquivos_ignorados"],
        )

    def _executar_processamento(self) -> None:
        self._botao_gerar.config(state="disabled")
        self._card_progresso.pack(fill="x", pady=(0, 12), before=self._barra_inferior)
        self._barra_progresso["value"] = 0
        self._label_mensagem.config(text="")

        modo = self._modo.get()
        pasta_saida = self._pasta_saida_efetiva()

        def on_progresso(evento) -> None:
            self._fila_eventos.put(("progresso", evento))

        def on_erro(caminho: str, motivo: str) -> None:
            self._fila_eventos.put(("erro", (caminho, motivo)))

        def worker() -> None:
            try:
                if modo == MODO_ARQUIVO_UNICO:
                    nome_arquivo = f"{self._t('prefixo_arquivo_saida')}_{datetime.datetime.now():%d_%H_%M}.txt"
                    resultado = separado.processar(
                        caminho_projeto=self._pasta_projeto,
                        caminho_saida_dir=pasta_saida,
                        nome_arquivo_saida=nome_arquivo,
                        extensoes=tuple(self._config["extensoes_separado"]),
                        pastas_ignoradas=self._config["pastas_ignoradas"],
                        arquivos_ignorados=self._config["arquivos_ignorados"],
                        on_progresso=on_progresso,
                        on_erro=on_erro,
                        arquivos_processaveis=self._arquivos_selecionados,
                        idioma=self._config.get("idioma", IDIOMA_PADRAO),
                    )
                else:
                    nome_subpasta = f"{self._t('prefixo_resumo_saida')}_{datetime.datetime.now():%d-%m-%Y_%Hh}"
                    pasta_saida_final = os.path.join(pasta_saida, nome_subpasta)
                    resultado = junto.processar(
                        caminho_projeto=self._pasta_projeto,
                        caminho_saida_dir=pasta_saida_final,
                        extensoes=tuple(self._config["extensoes_junto"]),
                        pastas_ignoradas=self._config["pastas_ignoradas"],
                        arquivos_ignorados=self._config["arquivos_ignorados"],
                        on_progresso=on_progresso,
                        on_erro=on_erro,
                        arquivos_processaveis=self._arquivos_selecionados,
                        idioma=self._config.get("idioma", IDIOMA_PADRAO),
                    )
                self._fila_eventos.put(("concluido", resultado))
            except Exception as e:
                self._fila_eventos.put(("falha", str(e)))

        self._thread_processamento = threading.Thread(target=worker, daemon=True)
        self._thread_processamento.start()
        self._after_fila = self.after(80, self._checar_fila_eventos)

    def _checar_fila_eventos(self) -> None:
        if self._fechando:
            return
        try:
            while True:
                tipo, dados = self._fila_eventos.get_nowait()

                if tipo == "progresso":
                    evento = dados
                    self._label_arquivo_atual.config(text=self._t("arquivo_atual", arquivo=evento.arquivo_atual))
                    self._label_contador.config(text=f"{evento.atual} / {evento.total}")
                    if evento.total > 0:
                        self._barra_progresso["value"] = (evento.atual / evento.total) * 100

                elif tipo == "erro":
                    caminho, motivo = dados
                    self._label_status_progresso.config(
                        text=self._t("aviso_nao_foi_possivel_ler", caminho=caminho, motivo=motivo),
                        fg=COR_AVISO,
                    )
                    self.after(1800, lambda: self._label_status_progresso.config(
                        text=self._t("processando_projeto"), fg=COR_TEXTO,
                    ))

                elif tipo == "concluido":
                    self._finalizar_processamento(dados)
                    return

                elif tipo == "falha":
                    self._botao_gerar.config(state="normal")
                    self._card_progresso.pack_forget()
                    messagebox.showerror(self._t("erro_processamento"), self._t("ocorreu_erro", erro=dados))
                    return

        except queue.Empty:
            pass

        self._after_fila = self.after(80, self._checar_fila_eventos)

    def _finalizar_processamento(self, resultado) -> None:
        self._botao_gerar.config(state="normal")
        self._card_progresso.pack_forget()

        nome_projeto = os.path.basename(self._pasta_projeto.rstrip(os.sep)) or self._pasta_projeto
        modo = self._modo.get()

        adicionar_entrada(
            nome_projeto=nome_projeto,
            quantidade_arquivos=resultado.processados,
            modo=modo,
            pasta_resultado=resultado.caminho_saida,
        )

        self._ultimo_resultado = resultado
        self._mostrar_resultado(resultado)
        self._persistir_config()

    def _mostrar_resultado(self, resultado) -> None:
        janela = tk.Toplevel(self)
        janela.title(self._t("transferencia_concluida"))
        janela.configure(bg=COR_FUNDO)
        janela.transient(self)
        janela.resizable(False, False)
        janela.protocol("WM_DELETE_WINDOW", janela.destroy)

        corpo = tk.Frame(janela, bg=COR_FUNDO)
        corpo.pack(fill="both", expand=True, padx=30, pady=26)

        tk.Label(
            corpo, text=self._t("transferencia_concluida_check"),
            font=("Segoe UI Variable Display", 17, "bold"),
            bg=COR_FUNDO, fg=COR_SUCESSO,
        ).pack(anchor="w")
        tk.Label(
            corpo, text=self._t("arquivos_gerados_sucesso"),
            font=("Segoe UI", 10), bg=COR_FUNDO, fg=COR_TEXTO_SECUNDARIO,
        ).pack(anchor="w", pady=(4, 18))

        resumo = tk.Frame(corpo, bg=COR_FUNDO)
        resumo.pack(fill="x")
        metricas = [
            (self._t("encontrados"), resultado.encontrados),
            (self._t("processados"), resultado.processados),
            (self._t("ignorados"), resultado.ignorados),
            (self._t("erros"), len(resultado.erros)),
        ]
        for coluna, (rotulo, valor) in enumerate(metricas):
            card = tk.Frame(
                resumo, bg=COR_FUNDO_CARD,
                highlightthickness=1, highlightbackground="#20314d",
            )
            card.grid(row=0, column=coluna, sticky="ew", padx=(0 if coluna == 0 else 4, 0))
            resumo.grid_columnconfigure(coluna, weight=1)
            tk.Label(
                card, text=str(valor), font=("Segoe UI", 16, "bold"),
                bg=COR_FUNDO_CARD, fg=COR_TEXTO,
            ).pack(pady=(10, 0))
            tk.Label(
                card, text=rotulo, font=("Segoe UI", 8, "bold"),
                bg=COR_FUNDO_CARD, fg=COR_TEXTO_SECUNDARIO,
            ).pack(pady=(1, 10), padx=10)

        tk.Label(
            corpo, text=self._t("salvo_em"), font=("Segoe UI", 9, "bold"),
            bg=COR_FUNDO, fg=COR_TEXTO,
        ).pack(anchor="w", pady=(18, 6))
        caminho_box = tk.Frame(corpo, bg=COR_FUNDO_CAMPO)
        caminho_box.pack(fill="x")
        tk.Label(
            caminho_box, text=resultado.caminho_saida, font=("Consolas", 9),
            bg=COR_FUNDO_CAMPO, fg=COR_TEXTO_SECUNDARIO,
            wraplength=540, justify="left", anchor="w", padx=12, pady=10,
        ).pack(fill="x")

        botoes = tk.Frame(corpo, bg=COR_FUNDO)
        botoes.pack(fill="x", pady=(20, 0))

        def abrir_resultado() -> None:
            caminho = resultado.caminho_saida
            alvo = caminho if os.path.isdir(caminho) else os.path.dirname(caminho)
            self._abrir_no_explorador(alvo)

        tk.Button(
            botoes, text=self._t("abrir_local_resultado"), command=abrir_resultado,
            bg=COR_DESTAQUE, fg="#ffffff", activebackground=COR_DESTAQUE_HOVER,
            activeforeground="#ffffff", relief="flat", bd=0,
            padx=16, pady=9, cursor="hand2", font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        tk.Button(
            botoes, text=self._t("fechar_aplicativo"), command=self._ao_fechar,
            bg=COR_FUNDO_CARD, fg=COR_TEXTO_SECUNDARIO, relief="flat",
            padx=14, pady=8, cursor="hand2", font=("Segoe UI", 9),
        ).pack(side="right", padx=(8, 0))
        tk.Button(
            botoes, text=self._t("continuar"), command=janela.destroy,
            bg=COR_FUNDO_CAMPO, fg=COR_TEXTO, relief="flat",
            padx=14, pady=8, cursor="hand2", font=("Segoe UI", 9),
        ).pack(side="right")

        janela.update_idletasks()
        largura = 650
        altura = max(390, janela.winfo_reqheight())
        x = self.winfo_rootx() + (self.winfo_width() - largura) // 2
        y = self.winfo_rooty() + (self.winfo_height() - altura) // 2
        janela.geometry(f"{largura}x{altura}+{max(0, x)}+{max(0, y)}")
        janela.lift()
        janela.focus_force()

    # ------------------------------------------------------------------
    # Diálogos auxiliares
    # ------------------------------------------------------------------

    def _focar_dialogo(self, classe: type[tk.Toplevel]) -> bool:
        for janela in self.winfo_children():
            if isinstance(janela, classe) and janela.winfo_exists():
                janela.deiconify()
                janela.lift()
                janela.focus_set()
                return True
        return False

    def _abrir_configuracoes(self) -> None:
        if self._focar_dialogo(JanelaConfiguracoes):
            return
        JanelaConfiguracoes(self, self._config, self._ao_salvar_configuracoes)

    def _ao_salvar_configuracoes(self, nova_config: dict) -> None:
        idioma_anterior = self._config.get("idioma", IDIOMA_PADRAO)
        self._config = nova_config
        self._limpar_selecao()
        self._persistir_config()

        if self._config.get("idioma", IDIOMA_PADRAO) != idioma_anterior:
            self.after_idle(self._reconstruir_interface)

    def _reconstruir_interface(self) -> None:
        if self._fechando:
            return

        self.title(self._t("titulo_janela", versao=VERSAO))
        for widget in list(self.winfo_children()):
            if not isinstance(widget, tk.Toplevel):
                widget.destroy()
        self._montar_layout()

    def _abrir_ajuda(self) -> None:
        if self._focar_dialogo(JanelaAjuda):
            return
        JanelaAjuda(self, idioma=self._config.get("idioma", IDIOMA_PADRAO))

    def _abrir_historico(self) -> None:
        if self._focar_dialogo(JanelaHistorico):
            return
        JanelaHistorico(self, idioma=self._config.get("idioma", IDIOMA_PADRAO))

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------

    def _persistir_config(self) -> None:
        self._config["ultima_pasta_projeto"] = self._pasta_projeto
        self._config["ultima_pasta_saida"] = self._pasta_saida
        self._config["ultimo_modo"] = self._modo.get()
        # Não grava as dimensões da tela inteira quando a janela está maximizada.
        if self.state() == "normal":
            self._config["janela_largura"] = self.winfo_width()
            self._config["janela_altura"] = self.winfo_height()
        salvar_config(self._config)

    def _ao_fechar(self) -> None:
        if self._fechando:
            return
        self._fechando = True

        try:
            self._persistir_config()
        except (OSError, tk.TclError):
            # Falha ao salvar preferências nunca deve impedir o encerramento.
            pass

        if self._after_fila is not None:
            try:
                self.after_cancel(self._after_fila)
            except tk.TclError:
                pass

        # Libera qualquer diálogo modal e encerra toda a árvore de janelas.
        for janela in self.winfo_children():
            if isinstance(janela, tk.Toplevel):
                try:
                    janela.grab_release()
                    janela.destroy()
                except tk.TclError:
                    pass

        self.quit()
        self.destroy()
