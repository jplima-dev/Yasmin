"""Ponto de entrada do Ink Notebook: python run.py [--port 8001] [--no-browser]"""
import argparse
import threading
import webbrowser

from app import create_app, config


def main():
    ap = argparse.ArgumentParser(description="Ink Notebook - notebook de conhecimento local")
    ap.add_argument("--host", default=config.HOST)
    ap.add_argument("--port", type=int, default=config.PORT)
    ap.add_argument("--no-browser", action="store_true", help="não abrir o navegador")
    args = ap.parse_args()

    app = create_app()
    url = f"http://{args.host}:{args.port}"
    print(f"\n  Ink Notebook rodando em {url}\n  Dados em: {config.DATA_DIR}\n  (Ctrl+C para encerrar)\n")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=args.host, port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
