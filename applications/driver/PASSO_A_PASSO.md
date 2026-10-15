# Drive2 — passo a passo

Este guia resume a instalação e o uso do Drive2. O cenário principal é um tablet Android executando Termux, acessado de forma privada por outros dispositivos através do Tailscale.

## 1. Entenda o fluxo

1. Os arquivos ficam fisicamente em `data/files` (ou no caminho definido por `DRIVE2_STORAGE_ROOT`).
2. O FastAPI serve a interface web e a API na porta `8000`.
3. O SQLite `drive2.db` guarda somente metadados, estados, filas e histórico — não guarda o conteúdo dos arquivos.
4. Um scanner detecta arquivos novos ou alterados e atualiza o índice.
5. Se uma pasta tiver uma política de backup, os arquivos dela entram na fila do Cloudflare R2.
6. Um arquivo só recebe o estado `SYNCED` após o Drive2 validar no R2 o tamanho e o SHA-256.
7. Gmail e Cloudflare R2 são opcionais; o servidor de arquivos funciona sem eles.

## 2. Faça um teste local primeiro

Requisitos: Python 3.11 ou superior.

```powershell
cd C:\caminho\para\drive2
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Para testar no Windows pela própria máquina, edite `.env` e use temporariamente:

```env
DRIVE2_HOST=127.0.0.1
DRIVE2_PORT=8000
DRIVE2_TAILSCALE_ONLY=true
R2_ENABLED=false
GMAIL_ENABLED=false
DRIVE2_AUTH_ENABLED=false
```

Inicie:

```powershell
python run.py
```

Abra `http://127.0.0.1:8000` e verifique a API em `http://127.0.0.1:8000/api/health`.

Para executar os testes automatizados:

```powershell
pip install pytest httpx
pytest -q
```

## 3. Prepare o tablet

1. Instale o Termux pelo F-Droid ou pelos releases oficiais.
2. Não misture Termux e complementos instalados por fontes diferentes.
3. No Termux, execute:

```bash
pkg update
pkg upgrade
pkg install python git
```

4. Confirme que o Python é 3.11 ou superior:

```bash
python --version
```

5. Opcionalmente, conceda acesso ao armazenamento compartilhado do Android:

```bash
termux-setup-storage
```

Mantenha o SQLite no armazenamento privado do Termux. Para a primeira instalação, mantenha também os arquivos em `data/files`.

## 4. Instale o Drive2 no tablet

Se houver um repositório Git:

```bash
cd "$HOME"
git clone <URL_DO_REPOSITORIO> drive2
cd drive2
```

Se recebeu um ZIP, extraia o conteúdo em `$HOME/drive2`.

Crie o ambiente e instale apenas o núcleo:

```bash
cd "$HOME/drive2"
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

## 5. Configure a primeira execução

Abra o arquivo:

```bash
nano "$HOME/drive2/.env"
```

Comece com esta configuração mínima:

```env
DRIVE2_HOST=0.0.0.0
DRIVE2_PORT=8000
DRIVE2_STORAGE_ROOT=data/files
DRIVE2_DATABASE=drive2.db
DRIVE2_TAILSCALE_ONLY=true
DRIVE2_AUTH_ENABLED=false
R2_ENABLED=false
GMAIL_ENABLED=false
```

Salve com `Ctrl+O`, Enter e saia com `Ctrl+X`.

## 6. Inicie e valide no tablet

```bash
cd "$HOME/drive2"
source .venv/bin/activate
python run.py
```

Em outra sessão do Termux:

```bash
cd "$HOME/drive2"
source .venv/bin/activate
python scripts/healthcheck.py
```

O retorno deve indicar `"status": "ok"`. No navegador do tablet, abra `http://127.0.0.1:8000`.

## 7. Configure o acesso remoto privado

1. Instale o Tailscale no tablet e no computador/celular que acessará o Drive2.
2. Entre na mesma conta/tailnet em todos os dispositivos.
3. Aceite a VPN no Android.
4. Descubra no aplicativo Tailscale o IP `100.x.y.z` do tablet.
5. No outro dispositivo, abra:

```text
http://100.x.y.z:8000
```

Com MagicDNS, também pode funcionar `http://nome-do-tablet:8000`.

Não abra a porta `8000` no roteador. Com `DRIVE2_TAILSCALE_ONLY=true`, o Drive2 aceita localhost e endereços Tailscale e rejeita acessos diretos pela LAN.

## 8. Ative uma senha, se necessário

Isso é recomendado quando outras pessoas ou dispositivos participam da mesma tailnet.

Gere o hash da senha:

```bash
cd "$HOME/drive2"
source .venv/bin/activate
python -m app.auth.password
```

Gere o segredo da sessão:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Atualize `.env`:

```env
DRIVE2_AUTH_ENABLED=true
DRIVE2_AUTH_USERNAME=admin
DRIVE2_AUTH_PASSWORD_HASH=HASH_GERADO
DRIVE2_AUTH_SECRET=SEGREDO_GERADO
DRIVE2_AUTH_COOKIE_SECURE=false
```

Reinicie o servidor. Use `DRIVE2_AUTH_COOKIE_SECURE=true` somente quando houver HTTPS.

## 9. Use a interface

1. **Arquivos:** crie pastas, envie, baixe, mova, renomeie e pesquise arquivos.
2. **Inbox:** use a pasta inicial `Inbox` para entradas rápidas.
3. **Favoritos e Recentes:** acompanhe itens importantes e usados recentemente.
4. **Lixeira:** excluir pela interface move primeiro para `data/trash`; é possível restaurar ou apagar definitivamente.
5. **Configurações:** consulte os valores públicos, logs e force a reindexação.
6. Arquivos copiados diretamente para `data/files` são detectados pelo scanner; por padrão, ele roda a cada 60 segundos.

## 10. Ative backup no Cloudflare R2 (opcional)

1. Crie um bucket privado no R2.
2. Crie credenciais `Object Read & Write` restritas a esse bucket.
3. Instale o módulo:

```bash
cd "$HOME/drive2"
source .venv/bin/activate
pip install -r requirements-cloud.txt
```

4. Configure `.env`:

```env
R2_ENABLED=true
R2_ACCOUNT_ID=SEU_ACCOUNT_ID
R2_ACCESS_KEY_ID=SUA_ACCESS_KEY
R2_SECRET_ACCESS_KEY=SEU_SECRET
R2_BUCKET=SEU_BUCKET
R2_ENDPOINT=https://SEU_ACCOUNT_ID.r2.cloudflarestorage.com
R2_REGION=auto
R2_PREFIX=drive2
```

5. Reinicie o Drive2.
6. Na área **Backups**, teste a conexão.
7. Adicione uma política para uma pasta, por exemplo `Documentos`. Nada é enviado ao R2 até uma política ser ativada.
8. Acompanhe a fila até o arquivo aparecer como `SYNCED`.
9. Faça um teste real de restauração antes de confiar no backup.

## 11. Ative arquivamento do Gmail (opcional)

1. No Google Cloud, ative a Gmail API.
2. Configure o Google Auth Platform e crie um cliente OAuth do tipo **Desktop app**.
3. Coloque o JSON em `config/gmail_credentials.json`.
4. Instale o módulo:

```bash
cd "$HOME/drive2"
source .venv/bin/activate
pip install -r requirements-gmail.txt
```

5. Configure `.env` de forma conservadora:

```env
GMAIL_ENABLED=true
GMAIL_CREDENTIALS_PATH=config/gmail_credentials.json
GMAIL_TOKEN_PATH=config/gmail_token.json
GMAIL_ARCHIVE_AFTER_DAYS=30
GMAIL_MAX_MESSAGE_MB=50
GMAIL_PROTECT_STARRED=true
GMAIL_PROTECT_IMPORTANT=true
GMAIL_TRASH_AFTER_BACKUP=false
```

6. Autorize a conta:

```bash
python -m app.email.cli auth
```

7. Teste sem remover nada do Gmail:

```bash
python -m app.email.cli archive --limit 5
```

8. Confira os `.eml` em `data/emails` e anexos em `data/attachments`.
9. Só depois de validar Gmail local e R2, considere `GMAIL_TRASH_AFTER_BACKUP=true`. Nessa modalidade, a mensagem só vai para a lixeira do Gmail após o `.eml` e anexos terem backup remoto validado.

## 12. Mantenha o servidor ativo

No Android, deixe Termux e Tailscale sem restrições de bateria e execute:

```bash
termux-wake-lock
```

Para iniciar automaticamente, instale Termux:Boot pela mesma fonte do Termux, abra o aplicativo uma vez e execute:

```bash
mkdir -p "$HOME/.termux/boot"
cp "$HOME/drive2/scripts/termux-boot-drive2" "$HOME/.termux/boot/20-drive2"
chmod +x "$HOME/.termux/boot/20-drive2"
```

O script pressupõe que o projeto está em `$HOME/drive2`.

## 13. Faça manutenção

Veja os logs:

```bash
tail -f "$HOME/drive2/logs/drive2.log"
tail -f "$HOME/drive2/logs/boot.log"
```

Faça backup consistente do SQLite:

```bash
cd "$HOME/drive2"
source .venv/bin/activate
python scripts/backup_db.py
```

Antes de atualizar:

```bash
python scripts/backup_db.py
git pull
pip install -r requirements.txt
```

Se usa módulos opcionais, reinstale o arquivo de requisitos correspondente e reinicie o servidor.

## 14. Diagnóstico rápido

- Não abre localmente: execute `python scripts/healthcheck.py` e consulte `logs/drive2.log`.
- Retorna `403` pela rede local: comportamento esperado com `DRIVE2_TAILSCALE_ONLY=true`; use o IP do Tailscale.
- Porta ocupada: confirme que não existem duas instâncias de `run.py`.
- Backup parado: confira `R2_ENABLED`, instalação do `boto3`, política da pasta e logs.
- Arquivo externo não apareceu: espere o scanner ou use o botão **Reindexar arquivos**.
- Estado `CLOUD_ONLY`: a cópia local sumiu, mas existe uma versão remota validada que pode ser restaurada.
- Erro de espaço/upload `507`: verifique o armazenamento livre no tablet.

## Ordem recomendada

Para reduzir riscos, siga esta sequência:

1. núcleo local;
2. acesso por Tailscale;
3. autenticação por senha;
4. inicialização automática;
5. backup R2 e teste de restauração;
6. Gmail sem lixeira automática;
7. somente então, se desejado, Gmail com lixeira após backup validado.
