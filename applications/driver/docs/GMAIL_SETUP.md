# Configuração do Gmail

Verificado em **21/09/2026** contra a documentação oficial atual do Gmail API e Google Auth Platform.

> Comece com `GMAIL_TRASH_AFTER_BACKUP=false`. Só habilite a lixeira automática depois de validar o arquivamento local e o R2.

## 1. Criar/selecionar projeto Google Cloud

### AÇÃO NO COMPUTADOR

Abra o Google Cloud Console e crie ou selecione um projeto para o Drive2.

## 2. Ativar Gmail API

No projeto, ative **Gmail API**.

Guia oficial atual:

https://developers.google.com/workspace/gmail/api/quickstart/python

## 3. Configurar Google Auth Platform

No console atual, vá para:

```text
Google Auth platform > Branding
```

Se ainda não estiver configurado, selecione **Get Started** e informe nome do app e e-mail de suporte.

### Conta pessoal Gmail

Para uma conta pessoal `@gmail.com`, use público **External**. Se o app estiver em modo **Testing**, adicione a sua própria conta como test user em **Audience**.

A documentação do Google informa que autorizações de test users em modo Testing podem expirar após 7 dias. Para um servidor permanente, revise o status de publicação e os requisitos de verificação aplicáveis ao seu uso.

### Google Workspace

Se você administra uma organização Workspace e o app será usado apenas internamente, a opção **Internal** pode estar disponível.

## 4. Escopo usado pelo Drive2

O Drive2 usa:

```text
https://www.googleapis.com/auth/gmail.modify
```

Esse escopo permite ler mensagens e movê-las para a lixeira, sem dar ao app a operação de exclusão permanente imediata que existe no escopo mais amplo `https://mail.google.com/`.

O Google classifica `gmail.modify` como **Restricted**. Se você distribuir/publicar o Drive2 para terceiros, verifique os requisitos atuais de OAuth verification e security assessment. O Google informa que apps que armazenam/transmitem dados de restricted scopes em servidores podem estar sujeitos a avaliação de segurança.

## 5. Criar OAuth Client

No Google Cloud Console:

```text
Google Auth platform > Clients
```

Selecione:

```text
Create Client
Application type: Desktop app
```

Nome sugerido:

```text
Drive2 Personal Server
```

Baixe o JSON de credenciais.

## 6. Colocar credencial no Drive2

### AÇÃO NO TABLET

Copie o JSON para:

```text
$HOME/drive2/config/gmail_credentials.json
```

O arquivo está no `.gitignore`.

## 7. Instalar dependências Gmail

### COMANDO NO TABLET

```bash
cd "$HOME/drive2"
source .venv/bin/activate
pip install -r requirements-gmail.txt
```

Se R2 também estiver ativo e você quiser que a remoção do Gmail só aconteça após backup remoto, use:

```bash
pip install -r requirements-full.txt
```

## 8. Configurar `.env`

### COMANDO NO TABLET

```bash
nano "$HOME/drive2/.env"
```

Comece de forma conservadora:

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

## 9. Autorizar a conta

O fluxo oficial para Desktop App usa navegador local.

### COMANDO NO TABLET

```bash
cd "$HOME/drive2"
source .venv/bin/activate
python -m app.email.cli auth
```

O navegador deve abrir para consentimento. Faça login na conta Gmail correta e aceite o escopo solicitado.

Após sucesso, o token fica em:

```text
config/gmail_token.json
```

Não compartilhe esse arquivo e nunca o envie ao Git.

### Se o navegador não abrir no tablet

Execute a autorização em um computador confiável com a mesma versão do projeto e as mesmas credenciais OAuth, gere `config/gmail_token.json` e transfira esse arquivo com segurança para o tablet. Não envie o token por repositório público.

## 10. O que o Drive2 arquiva

A busca usa a idade configurada e já exclui favoritos/importantes quando as proteções correspondentes estão ativas. Exemplo:

```text
older_than:30d -in:trash -is:starred -is:important
```

Antes de baixar o conteúdo completo, o Drive2 pede metadados leves para conferir labels e `sizeEstimate`. Mensagens acima de `GMAIL_MAX_MESSAGE_MB` são ignoradas, evitando carregar e-mails gigantes inteiros na RAM do tablet.

Para cada candidato:

1. `messages.get(format=raw)` baixa a mensagem RFC 822 completa;
2. mensagens `STARRED` são ignoradas quando a proteção está ligada;
3. mensagens `IMPORTANT` são ignoradas quando a proteção está ligada;
4. o `.eml` é salvo em `data/emails/`;
5. SHA-256 é validado;
6. anexos são extraídos para `data/attachments/<message_id>/` e também validados;
7. metadados entram no SQLite;
8. se R2 estiver habilitado, `.eml` e anexos são enviados e validados;
9. somente se `GMAIL_TRASH_AFTER_BACKUP=true` **e** o backup R2 foi validado, o Drive2 chama `users.messages.trash`.

Se você primeiro arquivar com a lixeira desativada e depois habilitar R2/lixeira, o processo é retomado: o Drive2 valida novamente os arquivos locais, conclui ou revalida o R2 e só depois move a mensagem no Gmail. Assim, o teste conservador inicial não “trava” a mensagem em um estado intermediário.

O código não usa exclusão permanente imediata.

## 11. Primeiro teste sem remover nada do Gmail

Confirme:

```env
GMAIL_TRASH_AFTER_BACKUP=false
```

Reinicie o Drive2 e execute:

### COMANDO NO TABLET

```bash
python -m app.email.cli archive --limit 5
```

ou use o botão **Arquivar elegíveis** na área Emails.

Depois confira:

```bash
find data/emails -maxdepth 1 -type f -name '*.eml' -ls
find data/attachments -type f -ls
```

Abra a interface e confira assunto/remetente/data.

## 12. Habilitar lixeira segura

Somente após testar R2 e o Gmail local:

```env
R2_ENABLED=true
GMAIL_TRASH_AFTER_BACKUP=true
```

Reinicie o servidor.

Agora uma mensagem só é movida para a lixeira do Gmail depois que `.eml` e todos os anexos extraídos daquela mensagem passarem pela validação remota R2.

## 13. Diagnóstico

### `Gmail ainda não foi autenticado`

```bash
python -m app.email.cli auth
```

### `No module named google...`

```bash
pip install -r requirements-gmail.txt
```

### `access_denied` / app não autorizado

- confirme que a conta está no público/test users corretos;
- confira o OAuth Client tipo Desktop;
- se alterou scopes, apague o token antigo e autorize novamente:

```bash
rm -f config/gmail_token.json
python -m app.email.cli auth
```

### token deixa de funcionar após alguns dias

Se o projeto estiver em modo OAuth **Testing**, verifique as regras atuais de expiração dos test users e o status de publicação no Google Auth Platform.

## Fontes oficiais

- Quickstart Python: https://developers.google.com/workspace/gmail/api/quickstart/python
- OAuth para apps instalados: https://developers.google.com/identity/protocols/oauth2/native-app
- Scopes Gmail: https://developers.google.com/workspace/gmail/api/auth/scopes
- `messages.get`: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get
- `messages.list`: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list
- `messages.trash`: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/trash
