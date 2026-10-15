# Mapa de funcionalidades

O `Bridge.pdf` divide o produto em fases. A interface principal segue agora o
MVP: conectar aparelhos, enviar conteúdo e entender o histórico sem precisar
conhecer detalhes de rede ou estruturas internas.

## Fluxo principal visível

| Área | Estado atual |
|---|---|
| Dispositivos | Cadastro por navegador, presença e revogação |
| Enviar arquivos | Seleção ou arrastar, envio imediato em blocos e progresso |
| Enviar texto/link | Conteúdo rápido entre aparelhos pareados |
| Histórico | Descrições em português, horário, estado, origem e destino |
| Conexões | Endereço local, identidade do Core e orientação curta |

## Fases do documento

| Fase | Escopo | Situação |
|---|---|---|
| 0 - Presença | Dois clientes identificados e online | Disponível |
| 1 - MVP local | Pareamento, LAN, arquivos, textos, links, Drop Zone e histórico | Fluxo principal |
| 2 - Uso pessoal | Tailscale, clipboard, fotos, favoritos e integridade | Parte disponível; integração nativa continua em evolução |
| 3 - Automação | Retomada, caixa temporária, pedir arquivo, atividade e som | Pausa/retomada no painel; demais fundações no Core/agentes |
| 4 - Controle | Tela, bloqueio e ações rápidas | Tela via WebRTC e controle de mouse/teclado do Windows por sessão; Android transmissor ainda exige implementação nativa |
| 5 - Equipes | Grupos, papéis, auditoria e Drive2 | Fundação experimental; fora da navegação principal |
| 6 - Produto público | Cloud/P2P, instaladores e serviço público | Não é o objetivo desta instalação pessoal |

## Decisões desta versão

- O destinatário não aprova cada arquivo: depois que o remetente escolhe o
  arquivo, a transferência e a verificação são automáticas.
- O navegador ainda precisa mostrar o seletor de arquivo, pois páginas web não
  podem ler arquivos pessoais sem uma escolha explícita.
- URLs remotas são validadas e aguardam um clique local para abrir em nova guia;
  a aba do Bridge permanece conectada.
- Recursos futuros continuam no backend para desenvolvimento, mas não disputam
  espaço com o fluxo diário.
- A tela é transmitida diretamente entre dois painéis e exige consentimento no
  navegador de origem em toda sessão. Se o navegador do Windows estiver fechado,
  o agente pode notificá-lo e abrir o painel para assumir a sessão. O controle
  do Windows é uma autorização separada, expira junto com a sessão e exige que
  o usuário escolha a tela inteira. Bloqueio, atividade e outras funções nativas
  mantêm as confirmações exigidas pelo Windows ou Android.
