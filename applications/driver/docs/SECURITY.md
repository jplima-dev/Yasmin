# Segurança

## Rede

Use o Drive2 atrás do Tailscale. Não faça port-forward da porta `8000` no roteador.

Por padrão:

```env
DRIVE2_TAILSCALE_ONLY=true
```

O middleware aceita apenas loopback e as faixas Tailscale oficiais `100.64.0.0/10` e `fd7a:115c:a1e0::/48`. Isso é importante porque escutar em `0.0.0.0` também abriria a porta para interfaces Wi-Fi/LAN do Android. O filtro não confia em `X-Forwarded-For`; usa o endereço observado pela conexão.

Se precisar de acesso por LAN, defina `DRIVE2_TAILSCALE_ONLY=false` conscientemente e habilite também a autenticação do Drive2.

## Autenticação do Drive2

Ela é opcional e desativada por padrão para facilitar a primeira instalação. Para ativar:

```bash
python -m app.auth.password
```

Copie o hash produzido para `.env` e gere um segredo aleatório:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Exemplo:

```env
DRIVE2_AUTH_ENABLED=true
DRIVE2_AUTH_USERNAME=admin
DRIVE2_AUTH_PASSWORD_HASH=pbkdf2_sha256$...
DRIVE2_AUTH_SECRET=valor_aleatorio_longo
```

Reinicie o servidor. A senha em texto puro não é salva no `.env`.

`DRIVE2_AUTH_COOKIE_SECURE=false` é necessário se você acessa por `http://nome-do-tablet:8000`. Se futuramente colocar HTTPS na frente do Drive2, mude para `true`.

## Segredos

Nunca versione:

- `.env`;
- `config/gmail_credentials.json`;
- `config/gmail_token.json`;
- chaves R2;
- backups do banco com dados pessoais.

## Permissões R2

Use `Object Read & Write` restrito ao bucket do Drive2. Não dê permissão administrativa se o sistema só precisa listar, ler, gravar e excluir objetos.

## Gmail

O Drive2 usa `gmail.modify` porque precisa ler mensagens e, opcionalmente, movê-las para a lixeira. Esse é um escopo classificado pelo Google como **restricted**. Se o aplicativo for distribuído/publicado para terceiros, verifique os requisitos atuais de verificação e avaliação de segurança do Google antes de fazê-lo.
