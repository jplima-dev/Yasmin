# Backup e sincronização

## Políticas

Nada é enviado ao R2 por padrão. Uma política protege um prefixo de caminho, por exemplo `Documentos` ou `Fotos/importantes`.

Ao ativar a política, arquivos locais já existentes naquele caminho são inseridos na fila. Novas mudanças são detectadas pelo scanner e também entram na fila.

## Estados

- `LOCAL_ONLY`: existe no tablet, versão atual ainda não validada na nuvem.
- `WAITING_BACKUP`: aguardando worker.
- `UPLOADING`: upload em andamento.
- `SYNCED`: versão atual validada no R2.
- `ERROR`: falhou; a fila agenda nova tentativa.
- `CLOUD_ONLY`: cópia local sumiu, mas existe versão remota validada.

## Integridade

O Drive2 calcula SHA-256 local e envia esse valor como metadata `drive2-sha256`. Depois do upload, executa `HeadObject` e verifica:

1. `ContentLength` igual ao tamanho local;
2. metadata `drive2-sha256` igual ao SHA-256 local.

O `ETag` é registrado apenas como informação; ele não é tratado como SHA-256.

Antes do upload o worker calcula novamente o SHA-256. Depois do envio, calcula o hash local outra vez. Se o arquivo tiver mudado enquanto era transferido — inclusive uma alteração de mesmo tamanho — ele **não** é marcado `SYNCED`; a fila registra erro e tenta a versão nova posteriormente.

## Retry

O atraso cresce exponencialmente a partir de 15 segundos e é limitado a 1 hora. A fila é SQLite, portanto sobreviverá a reinicializações.

## Restauração

A restauração baixa primeiro para `data/temp`, calcula SHA-256, valida tamanho e somente então move o arquivo para o caminho final.

## Se o tablet morrer completamente

A interface web principal fica no tablet, portanto não estará disponível com o aparelho desligado. Os objetos já validados continuam independentes no R2. As chaves seguem caminhos previsíveis, como:

```text
drive2/files/Documentos/trabalho.pdf
drive2/emails/<gmail_message_id>.eml
drive2/email-attachments/<gmail_message_id>/arquivo.pdf
```

Assim, mesmo sem o tablet, é possível recuperar os objetos diretamente pelo painel/ferramentas S3 do R2. Uma futura interface cloud pode usar o mesmo layout sem mudar o armazenamento. Guarde também cópias externas periódicas do SQLite se quiser preservar favoritos, histórico e catálogo além dos próprios arquivos.

## Banco SQLite

Crie uma cópia consistente com:

```bash
python scripts/backup_db.py
```

Para restaurar, **pare o servidor primeiro** e execute:

```bash
python scripts/restore_db.py backups/drive2-AAAAmmdd-HHMMSS.db
```

O script executa `PRAGMA integrity_check` e cria uma cópia do banco atual antes de substituí-lo.
