import os
import datetime

# EXTENSÕES QUE SERÃO LIDAS (basta adicionar ".txt" que ele começará a ler, NÃO USE IMAGENS)
EXTENSOES = (".php", ".css", ".js", ".py", ".html", ".txt", ".bat", ".txt", ".md")

# PASTAS QUE SERÃO IGNORADAS
IGNORAR_PASTAS = [
    "vendor",
    "PHPMailer-master",
    "node_modules",
    ".git",
    "__pycache__",
    ".env",
    "src",
    "Lib",
    "Include",
    "Scripts",
    ".gitignore",
    "pyvenv.cfg",
]

def ler_pastas(caminho, arquivo_saida, nivel=0):
    try:
        itens = os.listdir(caminho)
    except PermissionError:
        arquivo_saida.write(" " * nivel + "[Sem permissão]\n")
        return

    pastas = []
    arquivos = []

    for item in itens:
        caminho_completo = os.path.join(caminho, item)
        if os.path.isdir(caminho_completo):
            pastas.append(item)
        else:
            arquivos.append(item)

    pastas.sort()
    arquivos.sort()

    for item in pastas:
        caminho_completo = os.path.join(caminho, item)

        if item in IGNORAR_PASTAS:
            linha = " " * nivel + f"📁 (pasta ignorada) {item}\n"
            print(linha, end="")
            arquivo_saida.write(linha)
            continue

        linha = " " * nivel + f"📁 {item}\n"
        print(linha, end="")
        arquivo_saida.write(linha)

        ler_pastas(caminho_completo, arquivo_saida, nivel + 4)

    for item in arquivos:
        caminho_completo = os.path.join(caminho, item)

        if item.endswith(EXTENSOES):
            linha = " " * nivel + f"📄 {item}\n"
            print(linha, end="")
            arquivo_saida.write(linha)

            try:
                with open(caminho_completo, "r", encoding="utf-8") as f:
                    conteudo = f.read()

                cabecalho = " " * (nivel + 4) + "🧾 Conteúdo:\n"
                print(cabecalho, end="")
                arquivo_saida.write(cabecalho)

                for linha_arquivo in conteudo.splitlines():
                    linha_formatada = " " * (nivel + 6) + linha_arquivo + "\n"
                    print(linha_formatada, end="")
                    arquivo_saida.write(linha_formatada)

            except Exception as e:
                erro = " " * (nivel + 4) + f"[Erro ao ler arquivo: {e}]\n"
                print(erro, end="")
                arquivo_saida.write(erro)


# CAMINHO DO TEU PROJETO (pasta que deve ler)
pasta_principal = "C:\\Users\\Usuario\\OneDrive\\Desktop\\projeto"

# DETECTA DESKTOP (com ou sem OneDrive)
desktop = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
if not os.path.exists(desktop):
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")

# CRIA PASTA arquivos (para colocar os arquivos)
pasta_updates = os.path.join(desktop, "arquivos") 
os.makedirs(pasta_updates, exist_ok=True)

# NOME DO ARQUIVO COM DATA
agora = datetime.datetime.now()
nome_arquivo = f"arquivo_{agora.day}_{agora.hour}_{agora.minute}.txt" #mude o nome do arquivo se quiser (você pode mudar a extensão)

caminho_arquivo = os.path.join(pasta_updates, nome_arquivo) 

# GERA O ARQUIVO
with open(caminho_arquivo, "w", encoding="utf-8") as saida:
    titulo = f"📦 RESUMO DO PROJETO: {pasta_principal}\n\n"
    print(titulo)
    saida.write(titulo)

    ler_pastas(pasta_principal, saida)

print(f"\n✅ Arquivo salvo em:\n{caminho_arquivo}")