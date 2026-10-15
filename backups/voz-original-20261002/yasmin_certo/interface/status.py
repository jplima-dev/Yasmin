import threading
import tkinter as tk


class StatusYasm:
    """
    HUD da Yasm.

    Mostra apenas um texto no canto superior esquerdo:
        ● YAS FUNCIONANDO
        ● YAS DESLIGADA

    A interface fica sempre acima das outras janelas.
    """

    def __init__(self):
        self._root = None
        self._label = None
        self._thread = None
        self._pronta = threading.Event()
        self._fechando = threading.Event()
        self._estado_pendente = ("YAS FUNCIONANDO", "#00ff66")

    def iniciar(self):
        """
        Inicia a interface em uma thread separada.
        """
        if self._thread is not None and self._thread.is_alive():
            return

        self._pronta.clear()
        self._fechando.clear()

        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="yasm-status"
        )

        self._thread.start()

        # Espera a janela existir antes de continuar.
        self._pronta.wait(timeout=3.0)

    def _loop(self):
        try:
            self._root = tk.Tk()
        except tk.TclError:
            self._pronta.set()
            return

        # --------------------------------------------------------
        # Janela invisível como moldura do texto
        # --------------------------------------------------------

        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)

        # Fundo que será tratado como transparente.
        fundo_transparente = "#010101"

        try:
            self._root.attributes(
                "-transparentcolor",
                fundo_transparente
            )
        except tk.TclError:
            # Algumas configurações do Windows podem não aceitar
            # transparentcolor. O texto continuará funcionando.
            pass

        self._root.configure(
            bg=fundo_transparente
        )

        # --------------------------------------------------------
        # Texto
        # --------------------------------------------------------

        self._label = tk.Label(
            self._root,
            text="● YAS FUNCIONANDO",
            font=("Segoe UI", 12, "bold"),
            fg="#00ff66",
            bg=fundo_transparente,
            padx=0,
            pady=0,
            bd=0,
            highlightthickness=0
        )

        self._label.pack()

        # --------------------------------------------------------
        # Posicao: canto superior esquerdo
        # --------------------------------------------------------

        self._root.update_idletasks()

        margem_x = 12
        margem_y = 8

        largura = self._root.winfo_reqwidth()
        altura = self._root.winfo_reqheight()

        self._root.geometry(
            f"{largura}x{altura}+{margem_x}+{margem_y}"
        )

        # --------------------------------------------------------
        # Foco nunca vai para o HUD
        # --------------------------------------------------------

        try:
            self._root.attributes(
                "-toolwindow",
                True
            )
        except tk.TclError:
            pass

        self._pronta.set()

        # Atualiza o estado inicial.
        texto, cor = self._estado_pendente
        self._label.config(
            text=f"● {texto}",
            fg=cor
        )

        self._root.after(50, self._aplicar_pendente)
        try:
            self._root.mainloop()
        finally:
            self._label = None
            self._root = None
            self._pronta.clear()

    def _aplicar_pendente(self):
        # Todas as chamadas Tk acontecem na thread que criou a janela.
        if self._fechando.is_set():
            self._root.destroy()
            return
        texto, cor = self._estado_pendente
        self._label.config(text=f"● {texto}", fg=cor)
        self._root.after(50, self._aplicar_pendente)

    def _atualizar(self, texto, cor):
        self._estado_pendente = (texto, cor)

    def funcionando(self):
        """
        Mostra:
        ● YAS FUNCIONANDO
        """
        self._estado_pendente = (
            "YAS FUNCIONANDO",
            "#00ff66"
        )

        self._atualizar(
            "YAS FUNCIONANDO",
            "#00ff66"
        )

    def desligada(self):
        """
        Mostra:
        ● YAS DESLIGADA
        """
        self._estado_pendente = (
            "YAS DESLIGADA",
            "#ff3030"
        )

        self._atualizar(
            "YAS DESLIGADA",
            "#ff3030"
        )

    def fechar(self):
        """
        Fecha completamente o HUD.
        """
        self._fechando.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)


# ============================================================
# INSTANCIA GLOBAL
# ============================================================

status_yasm = StatusYasm()


def iniciar():
    status_yasm.iniciar()


def funcionando():
    status_yasm.funcionando()


def desligada():
    status_yasm.desligada()


def fechar():
    status_yasm.fechar()


# ============================================================
# TESTE DIRETO
# ============================================================

if __name__ == "__main__":
    iniciar()

    import time

    time.sleep(5)

    desligada()

    time.sleep(5)

    fechar()
