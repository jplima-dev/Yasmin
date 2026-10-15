# Arquitetura do Drive2

## Visão geral

```text
Navegador
   │
   │ HTTP dentro da tailnet
   ▼
FastAPI ──────────────── Web estática
   │  └─ filtro localhost/Tailscale + auth opcional
   │
   ├── FileService ───── data/files
   │       │
   │       └── scanner SHA-256
   │
   ├── SQLite ────────── drive2.db
   │       ├── files
   │       ├── backup_policies
   │       ├── sync_queue
   │       ├── sync_history
   │       ├── trash_entries
   │       └── email_*
   │
   ├── SyncService ───── Cloudflare R2 (opcional)
   │
   └── GmailService ──── Gmail API (opcional)
```

## Decisões principais

**Arquivos não ficam no SQLite.** O banco contém apenas metadados e estados. Isso simplifica recuperação e evita bancos gigantes.

**Hash sob demanda.** O scanner compara tamanho e `mtime`. SHA-256 é recalculado apenas para arquivo novo, alterado ou ainda sem hash.

**Fila persistente.** A sincronização não depende de uma requisição web permanecer aberta. O estado fica em `sync_queue`, e um worker processa um item por vez para reduzir RAM/CPU.

**R2 é cópia, não origem primária.** `cloud_available=1` significa que a versão atual foi validada no R2. Um arquivo local ausente e protegido passa a `CLOUD_ONLY`.

**Delete local é lixeira primeiro.** A UI move o conteúdo para `data/trash`. A cópia remota não é apagada automaticamente, reduzindo risco de perda acidental.

## Fluxo de alteração

```text
arquivo novo/alterado
  ↓
scanner detecta size/mtime diferente
  ↓
SHA-256
  ↓
SQLite atualizado
  ↓
se política de backup combinar: WAITING_BACKUP
  ↓
worker R2
  ↓
upload
  ↓
HEAD do objeto + metadata sha256 + ContentLength
  ↓
SYNCED
```

## Fluxo Gmail

```text
messages.list (regra de idade)
  ↓
messages.get(format=raw)
  ↓
proteção STARRED/IMPORTANT
  ↓
salva .eml temporário
  ↓
valida SHA-256 local
  ↓
extrai anexos + valida hashes
  ↓
opcional: backup R2 de .eml + anexos
  ↓
SQLite
  ↓
se configurado E backup R2 validado: users.messages.trash
```

## Tablet offline

A interface principal roda no tablet, então ela não pode ser aberta se o tablet estiver desligado. Porém, os objetos protegidos continuam no R2. O banco guarda `cloud_key` e SHA-256 para restauração. Uma futura interface cloud pode consumir um catálogo exportado sem mudar o modelo de armazenamento.

## Limites deliberados da v1.0

- Sem edição colaborativa de documentos.
- Sem versionamento histórico completo de cada arquivo; R2 protege a versão sincronizada atual.
- Sem exposição pública do frontend pela internet.
- Gmail não roda em cron por padrão; a ação é manual para evitar exclusões inesperadas.
