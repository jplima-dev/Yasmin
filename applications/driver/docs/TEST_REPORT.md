# Relatório de testes — Drive2 v1.0.0

Data: **21/09/2026**

## Testes automatizados

Comando:

```bash
pytest -q
```

Resultado final:

```text
12 passed
```

Cobertura direta dos testes:

- bloqueio de path traversal;
- criar, renomear, mover e excluir arquivos;
- conflitos de nomes;
- SHA-256 conhecido;
- lixeira e restauração;
- schema/migração SQLite;
- políticas de backup e fila persistente;
- remapeamento de caminhos preservando metadados;
- PBKDF2 de senha;
- sanitização/hash de anexos;
- arquivo alterado durante upload não pode virar `SYNCED`;
- retomada de e-mail local: R2 primeiro, lixeira Gmail depois;
- filtro de origem aceita loopback/Tailscale e bloqueia LAN/público.

Também foram executados `python -m compileall -q app` e `node --check web/js/app.js`.

## Testes de integração com servidor real

O FastAPI foi iniciado em processos separados com diretórios e SQLite temporários. Foram verificados:

```text
GET    /api/health
POST   /api/directories
POST   /api/upload
GET    /api/files
PATCH  /api/files/rename
PATCH  /api/files/move
PATCH  /api/favorites
POST   /api/index/rebuild
DELETE /api/files
GET    /api/trash
POST   /api/trash/{id}/restore
GET    /api/backup/queue
GET    /api/files/cloud
POST   /api/backup/restore (falha controlada 503 sem R2)
GET    /api/emails/{id}/download
GET    /
```

Cenários adicionais validados:

- alteração feita diretamente no disco é detectada e muda o hash;
- renomear arquivo de pasta protegida atualiza/recria a entrada de fila;
- enviar para lixeira cancela upload pendente;
- restaurar arquivo protegido sem cloud volta para a fila;
- item `CLOUD_ONLY` pode ser favoritado sem existir localmente;
- `../` recebe erro em vez de escapar da raiz;
- autenticação habilitada retorna `401` antes do login e libera a API depois da sessão válida;
- e-mail `.eml` armazenado pode ser baixado pela API.

## Simulações de segurança de integridade

Um cliente R2 falso alterou um arquivo **durante** o upload mantendo o mesmo tamanho. O Drive2 detectou a mudança no segundo SHA-256, marcou `ERROR`, manteve `cloud_available=0` e preservou a fila para retry.

Um Gmail/R2 falso foi usado para simular o fluxo recomendado “arquivar local primeiro, habilitar R2/lixeira depois”. A mensagem só recebeu a operação de lixeira depois do backup validado.

## Integrações externas não executadas com conta real

Não foram usadas credenciais reais do usuário. Portanto, estes itens precisam do teste manual documentado no tablet:

- Cloudflare R2 real;
- OAuth/Gmail real e movimentação real para lixeira;
- conexão real entre tablet Android e notebook pelo Tailscale;
- Termux:Boot e comportamento do fabricante com a tela desligada.

Não foi simulado “sucesso” desses serviços. Os guias de teste estão em `CLOUDFLARE_SETUP.md`, `GMAIL_SETUP.md`, `TAILSCALE_SETUP.md` e `TABLET_SETUP.md`.
