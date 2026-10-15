# Equipe, Cloud/P2P e Drive2

## Equipe ou loja

O painel cria equipes e associa aparelhos aos papéis `owner`, `manager`, `member`
e `viewer`. Isso já permite modelar o inventário e persistir a intenção de acesso.
Antes de uso real por funcionários, implemente:

1. identidade de usuário separada de identidade de aparelho;
2. login forte e recuperação;
3. middleware RBAC em toda rota;
4. escopo por `team_id` em toda consulta;
5. trilha de auditoria imutável/exportável;
6. testes de isolamento entre duas equipes.

Até esses itens existirem, trate o modo equipe como laboratório local.

## Cloud/P2P

`POST /api/signals` retransmite `offer`, `answer`, candidatos `ice`, recusa e fim
de sessão ao WebSocket do destino. O painel já usa esse canal para compartilhar
uma track de tela entre dois navegadores, vinculada a uma sessão iniciada pelo
receptor e aprovada localmente no transmissor.

Ainda faltam para uso em redes arbitrárias e outros tipos de P2P:

- usar DataChannel para transferência de arquivos;
- configurar STUN e um TURN autenticado para redes restritas;
- adicionar streaming nativo no agente Windows e encoder no Android;
- persistir métricas de qualidade sem guardar o conteúdo da tela.

Não use servidor TURN público com credenciais fixas.

## Drive2

Ao clicar **Arquivar último recebido**, o Bridge copia o arquivo concluído para:

```text
.data/drive2-outbox/<transfer-id>/
  arquivo.ext
  manifest.json
```

O manifesto contém ID, nome, horário e SHA-256. O conector Drive2 deve:

1. observar diretórios completos (manifesto por último);
2. validar novamente o SHA-256;
3. enviar de forma idempotente usando `transfer_id`;
4. mover para `processed/` apenas após confirmação do Drive2;
5. registrar erro sem apagar o original.

Essa fronteira mantém o Bridge independente da API futura do Drive2.
