import os
import datetime

# EXTENSÕES QUE SERÃO LIDAS (basta adicionar ".txt" que ele começará a ler, NÃO USE IMAGENS)
EXTENSOES = (".php", ".css", ".js")

# PASTAS QUE SERÃO IGNORADAS
IGNORAR_PASTAS = [
    "vendor",
    "PHPMailer-master",
    "node_modules",
    ".git",
    "__pycache__",
    "src",
    ".env",
]

def processar_pastas(origem, destino, nivel=0):
    try:
        itens = os.listdir(origem)
    except PermissionError:
        return

    for item in itens:
        caminho_origem = os.path.join(origem, item)

        if item in IGNORAR_PASTAS and os.path.isdir(caminho_origem):
            print(" " * nivel + f"📁 (ignorada) {item}")
            continue

        if os.path.isdir(caminho_origem):
            caminho_destino = os.path.join(destino, item)
            os.makedirs(caminho_destino, exist_ok=True)

            print(" " * nivel + f"📁 {item}")

            processar_pastas(caminho_origem, caminho_destino, nivel + 4)

        elif item.endswith(EXTENSOES):
            print(" " * nivel + f"📄 {item}")

            try:
                with open(caminho_origem, "r", encoding="utf-8") as f:
                    conteudo = f.read()

                nome_txt = item + ".txt"
                caminho_destino = os.path.join(destino, nome_txt)

                with open(caminho_destino, "w", encoding="utf-8") as novo_arquivo:
                    novo_arquivo.write(f"📄 Arquivo original: {item}\n\n")
                    novo_arquivo.write("🧾 Conteúdo:\n\n")
                    novo_arquivo.write(conteudo)

            except Exception as e:
                print(" " * (nivel + 2) + f"[Erro: {e}]")

# CAMINHO DO TEU PROJETO (pasta que deve ler)
pasta_principal = "C:\\Users\\Usuario\\OneDrive\\Desktop\\projeto"

# DETECTA DESKTOP (com ou sem OneDrive)
desktop = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
if not os.path.exists(desktop):
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")

# CRIA PASTA updates_sistema (para colocar os arquivos)
pasta_updates = os.path.join(desktop, "updates_sistema")
os.makedirs(pasta_updates, exist_ok=True)

# NOME DO ARQUIVO COM DATA
agora = datetime.datetime.now()
nome_resumo = f"resumo_{agora.day:02d}-{agora.month:02d}-{agora.year}_{agora.hour}h" #mude o nome se quiser

pasta_resumo = os.path.join(pasta_updates, nome_resumo)
os.makedirs(pasta_resumo, exist_ok=True)

# ===== EXECUÇÃO =====
print(f"\n📦 Criando resumo em: {pasta_resumo}\n")

processar_pastas(pasta_principal, pasta_resumo)

print("\n✅ Tudo pronto!")