# Troubleshooting

## Drive2 não abre nem no tablet

### COMANDO NO TABLET

```bash
cd "$HOME/drive2"
source .venv/bin/activate
python scripts/healthcheck.py
```

Se falhar:

```bash
tail -n 100 logs/drive2.log
```

Inicie manualmente para ver o erro no terminal:

```bash
python run.py
```

## `Address already in use`

Existe outro processo usando a porta.

```bash
ps -ef | grep '[r]un.py'
```

Encerre o processo antigo ou altere `DRIVE2_PORT` no `.env`.

## Funciona em `127.0.0.1`, mas não pelo Tailscale

Confirme:

```env
DRIVE2_HOST=0.0.0.0
```

Reinicie o Drive2. Depois confira se computador e tablet estão na mesma tailnet e se Tailscale está conectado.

## Pela LAN recebo `403`, mas localhost funciona

Isso é esperado com:

```env
DRIVE2_TAILSCALE_ONLY=true
```

Acesse pelo IP/nome Tailscale. Para teste deliberado pela rede local, altere para `false`, reinicie e prefira manter `DRIVE2_AUTH_ENABLED=true`.

## Servidor morre com a tela apagada

- defina Termux e Tailscale como `Unrestricted/Sem restrições` quando a opção existir;
- use `termux-wake-lock`;
- instale/configure Termux:Boot;
- alguns fabricantes ainda podem matar processos agressivamente.

## Upload falha com 507

O Drive2 usa `507` para erros de espaço/IO. Confira espaço livre no painel e no Android.

## Arquivo alterado fora da interface não atualizou

O scanner roda a cada `DRIVE2_SCAN_INTERVAL_SECONDS` (mínimo 15 s). Para forçar:

```bash
curl -X POST http://127.0.0.1:8000/api/index/rebuild
```

## Backup fica aguardando

- R2 está habilitado?
- `boto3` foi instalado?
- o servidor foi reiniciado após editar `.env`?
- a política cobre o caminho?

```bash
tail -n 100 logs/drive2.log
```

## Backup dá `ERROR`

Veja **Backups > Fila/Histórico** e logs. O item continuará persistido e novas tentativas serão agendadas.

## Arquivo local sumiu, mas está `CLOUD_ONLY`

Isso significa que o Drive2 ainda tem uma cópia R2 validada para a versão indexada. Use a ação Restaurar ou `/api/backup/restore`.

## SQLite `database is locked`

Não rode vários servidores Drive2 usando o mesmo banco. O SQLite está em WAL e `busy_timeout`, mas duas instâncias do servidor podem gerar contenção desnecessária.

Verifique processos:

```bash
ps -ef | grep '[r]un.py'
```

## SQLite parece corrompido

Pare o servidor e verifique:

```bash
python - <<'PY'
import sqlite3
c=sqlite3.connect('drive2.db')
print(c.execute('PRAGMA integrity_check').fetchone()[0])
c.close()
PY
```

Se não retornar `ok`, restaure um backup com `scripts/restore_db.py`.

## Login entra em loop

Se `DRIVE2_AUTH_ENABLED=true`, confira se ambos existem:

```env
DRIVE2_AUTH_PASSWORD_HASH=...
DRIVE2_AUTH_SECRET=...
```

Se você mudou a senha ou secret, cookies antigos deixam de ser válidos. Feche/reabra o site ou limpe os cookies do endereço do Drive2.

## Gmail não autentica

Veja `docs/GMAIL_SETUP.md`. Em especial, confira Gmail API habilitada, OAuth Client Desktop, Audience/Test users e token.
