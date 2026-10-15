# Configuração do Cloudflare R2

Verificado em **21/09/2026** contra a documentação oficial atual do Cloudflare R2.

O R2 é opcional. O Drive2 continua funcionando localmente sem ele.

## 1. Entrar/criar conta

### AÇÃO NO COMPUTADOR

Entre em https://dash.cloudflare.com/ ou crie uma conta.

## 2. Ativar R2

No dashboard atual, vá para:

```text
Storage & databases > R2 > Overview
```

Se a conta ainda não tiver R2 habilitado, siga o fluxo exibido pelo Cloudflare. A documentação atual informa que R2 precisa estar ativado/adquirido na conta antes da geração de credenciais S3.

## 3. Criar bucket

Na tela R2, selecione **Create bucket**.

Sugestão de nome:

```text
drive2-backup
```

ou algo único:

```text
drive2-backup-gustavo
```

Configuração recomendada:

- bucket **privado**;
- localização padrão/automática, a menos que você tenha requisito de jurisdição;
- storage class padrão `Standard`, se essa escolha aparecer;
- não habilitar acesso público para o Drive2.

Guarde o nome exato do bucket.

## 4. Criar credenciais S3

Na página R2 **Overview**, em **API Tokens**, selecione **Manage** e crie um token.

Use:

```text
Permission: Object Read & Write
Scope: bucket específico do Drive2
```

Não use permissão administrativa se não for necessária.

Após criar, copie imediatamente:

- **Access Key ID**;
- **Secret Access Key**.

O Cloudflare informa que o Secret Access Key não poderá ser exibido novamente depois dessa etapa.

## 5. Account ID e endpoint

O endpoint padrão S3 é:

```text
https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

O Account ID aparece no dashboard R2 e também compõe o endpoint mostrado na criação do token.

Buckets com jurisdição específica usam endpoint específico, por exemplo `.eu.r2.cloudflarestorage.com`, `.us...` ou `.fedramp...`. Use exatamente o endpoint exibido pela conta/bucket.

Para SDKs S3, a região do R2 é:

```text
auto
```

## 6. Instalar o cliente R2 no tablet

### COMANDO NO TABLET

```bash
cd "$HOME/drive2"
source .venv/bin/activate
pip install -r requirements-cloud.txt
```

## 7. Configurar `.env`

### COMANDO NO TABLET

```bash
cd "$HOME/drive2"
nano .env
```

Preencha:

```env
R2_ENABLED=true
R2_ACCOUNT_ID=SEU_ACCOUNT_ID
R2_ACCESS_KEY_ID=SUA_ACCESS_KEY
R2_SECRET_ACCESS_KEY=SEU_SECRET
R2_BUCKET=drive2-backup
R2_ENDPOINT=https://SEU_ACCOUNT_ID.r2.cloudflarestorage.com
R2_REGION=auto
R2_PREFIX=drive2
```

Nunca coloque valores reais no Git. O `.env` já está no `.gitignore`.

Reinicie o Drive2.

## 8. Testar conexão

### COMANDO NO TABLET

Com o ambiente virtual ativo:

```bash
python -c "from app.backup.r2 import R2Client; print(R2Client().test_connection())"
```

Esperado:

```text
{'ok': True, ...}
```

Também existe o botão **Testar conexão** na área Backups da interface.

## 9. Upload de teste

### COMANDO NO TABLET

```bash
cd "$HOME/drive2"
mkdir -p data/files/TesteR2
printf 'drive2-r2-test\n' > data/files/TesteR2/teste.txt
```

Com o servidor rodando, reindexe:

```bash
curl -X POST http://127.0.0.1:8000/api/index/rebuild
```

Ative backup apenas para a pasta de teste:

```bash
curl -X PUT http://127.0.0.1:8000/api/backup/policies \
  -H 'Content-Type: application/json' \
  -d '{"path_prefix":"TesteR2","enabled":true}'
```

Processe um item imediatamente:

```bash
curl -X POST http://127.0.0.1:8000/api/backup/run-one
```

Consulte:

```bash
curl 'http://127.0.0.1:8000/api/files?path=TesteR2'
```

O arquivo deve chegar a `SYNCED` somente depois da validação remota.

## 10. Download/restauração de teste

Mova o arquivo para a lixeira pela interface e depois restaure da nuvem pela ação disponível quando o índice o identificar como `CLOUD_ONLY`.

Também pode usar:

```bash
curl -X POST http://127.0.0.1:8000/api/backup/restore \
  -H 'Content-Type: application/json' \
  -d '{"path":"TesteR2/teste.txt"}'
```

O Drive2 baixa para temporário, valida SHA-256 e tamanho e só então move para o caminho final.

## 11. Remover o objeto de teste do R2

Depois de terminar os testes e confirmar que você não precisa dele:

### COMANDO NO TABLET

```bash
python - <<'PY'
from app.backup.r2 import R2Client
from app.database.db import db_session
from app.database.repository import get_file

with db_session() as conn:
    item = get_file(conn, "TesteR2/teste.txt")
if item and item.get("cloud_key"):
    R2Client().delete(item["cloud_key"])
    with db_session() as conn:
        conn.execute(
            "UPDATE files SET cloud_available=0, cloud_key=NULL, last_backup=NULL, sync_status='LOCAL_ONLY' WHERE relative_path=?",
            ("TesteR2/teste.txt",),
        )
    print("Objeto remoto de teste removido e índice atualizado:", item["cloud_key"])
else:
    print("Objeto remoto não encontrado no índice")
PY
```

Depois remova a política `TesteR2` pela interface e apague os arquivos de teste locais. O exemplo atualiza o SQLite junto com a remoção remota para não deixar um falso estado `cloud_available`.

## 12. Diagnóstico de erros comuns

### `403`, `AccessDenied`

- token sem `Object Read & Write`;
- token limitado a outro bucket;
- Access Key/Secret incorretos.

### erro de endpoint/assinatura

- endpoint não corresponde ao Account ID;
- bucket com jurisdição usando endpoint padrão;
- `R2_REGION` diferente de `auto`.

### `No module named boto3`

```bash
pip install -r requirements-cloud.txt
```

### fila fica `WAITING_BACKUP`

- confirme `R2_ENABLED=true`;
- reinicie o servidor depois de editar `.env`;
- confira `logs/drive2.log`.

## 13. Chave comprometida

Crie um novo token R2 com as mesmas permissões mínimas, troque `R2_ACCESS_KEY_ID` e `R2_SECRET_ACCESS_KEY` no `.env`, reinicie o Drive2 e teste a conexão. Só então revogue a chave antiga.

## 14. Revogar credenciais

No dashboard R2, abra o gerenciamento de **API Tokens**, localize o token e revogue/exclua-o. O Drive2 deixará de sincronizar até receber novas credenciais.

## 15. Ver uso do armazenamento

No dashboard:

```text
R2 > seu bucket > Metrics
```

A documentação atual informa que a aba **Metrics** mostra métricas de operações e armazenamento e permite selecionar janela de tempo.

## Fontes oficiais

- S3/R2: https://developers.cloudflare.com/r2/get-started/s3/
- Tokens: https://developers.cloudflare.com/r2/api/tokens/
- Compatibilidade S3: https://developers.cloudflare.com/r2/api/s3/api/
- Uploads: https://developers.cloudflare.com/r2/objects/upload-objects/
- Métricas: https://developers.cloudflare.com/r2/platform/metrics-analytics/
