"""Paleta e estilos compartilhados pelas janelas do aplicativo."""
from tkinter import ttk

COR_FUNDO = "#0b1220"
COR_FUNDO_CARD = "#111c2e"
COR_FUNDO_CAMPO = "#18263d"
COR_TEXTO = "#f4f7fb"
COR_TEXTO_SECUNDARIO = "#9fb0c8"
COR_SUCESSO = "#4ade80"
COR_ERRO = "#fb7185"
COR_AVISO = "#fbbf24"
COR_DESTAQUE = "#4f8cff"
COR_DESTAQUE_HOVER = "#3978e6"


def configurar_tema(parent):
    estilo = ttk.Style(parent)
    # O tema nativo do Windows ignora algumas cores de Treeview.
    if estilo.theme_use() != "clam":
        estilo.theme_use("clam")
    estilo.configure("Leitor.Treeview", background=COR_FUNDO_CARD,
                     fieldbackground=COR_FUNDO_CARD, foreground=COR_TEXTO,
                     bordercolor="#20314d", lightcolor=COR_FUNDO_CARD,
                     darkcolor=COR_FUNDO_CARD, rowheight=30, font=("Segoe UI", 10))
    estilo.configure("Leitor.Treeview.Heading", background=COR_FUNDO_CAMPO,
                     foreground=COR_TEXTO_SECUNDARIO, relief="flat",
                     font=("Segoe UI", 9, "bold"), padding=(10, 9))
    estilo.map("Leitor.Treeview", background=[("selected", "#244573")],
               foreground=[("selected", COR_TEXTO)])
    estilo.map("Leitor.Treeview.Heading", background=[("active", "#20314d")])
    for orientacao in ("Vertical", "Horizontal"):
        nome = f"Leitor.{orientacao}.TScrollbar"
        estilo.configure(nome, background=COR_FUNDO_CAMPO, troughcolor=COR_FUNDO_CARD,
                         bordercolor=COR_FUNDO_CARD, arrowcolor=COR_TEXTO_SECUNDARIO,
                         lightcolor=COR_FUNDO_CAMPO, darkcolor=COR_FUNDO_CAMPO, relief="flat")
        estilo.map(nome, background=[("active", "#244573")])
