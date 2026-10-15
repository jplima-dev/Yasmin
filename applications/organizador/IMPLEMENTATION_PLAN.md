# Painel Pessoal — plano de implementação

Data: 19/09/2026. Estado: MVP 0.1 implementado; Quadros integrado a pedido do usuário; homologação ampliada permanece no backlog.

Referência: [ARCHITECTURE.md](ARCHITECTURE.md). A solicitação posterior autorizou programar o painel e integrar o Notas Flutuantes original. Os módulos do MVP estão implementados; os resultados de validação estão em [VERIFICATION.md](VERIFICATION.md). A lista detalhada abaixo preserva os critérios originais de homologação, incluindo verificações ainda não executadas; uma caixa aberta não significa que o módulo correspondente não possui código.

## Registro da implementação autorizada

- [x] Layout, rotas por módulo, temas e componentes compartilhados.
- [x] IndexedDB, repositório, validação, transações, revisão e notificações entre abas.
- [x] Projetos, tarefas, subtarefas e notas com relações e exclusões consistentes.
- [x] Dashboard, progresso derivado, atividade recente e alertas por regras.
- [x] Busca global em lotes, resultados parciais e atalhos.
- [x] Backup JSON com validação, prévia, mesclagem e substituição transacional.
- [x] Fonte do Notas Flutuantes compartilhada por junction, visualizador integrado e vínculo quadro/projeto.
- [x] Build de produção incluindo os arquivos originais e a licença do Notas Flutuantes.
- [x] 18 testes automatizados, verificações de IndexedDB real e benchmark com 5.002 registros.
- [ ] Homologação ampliada em Firefox/Safari, ensaio com 20 mil itens e medições sistemáticas de memória.

O módulo Quadros entregue usa o código original; as tarefas da futura versão 0.3 abaixo descrevem uma possível evolução nativa e não devem ser executadas como uma reescrita automática do que já funciona.

## Como executar este plano

Cada tarefa tem ID, dependências e resultado verificável. Só começar uma tarefa quando suas dependências estiverem concluídas. “Fase anterior” nunca substitui uma dependência: os IDs abaixo identificam o trabalho necessário. Os gates de saída reúnem os critérios de cada etapa.

Executar um incremento de cada vez e manter o projeto utilizável ao final das fases. Não criar código, stores, dependências ou itens de menu de versões futuras. As tarefas futuras são escopo previsto; devem ser refinadas quando sua versão começar, à luz do uso real.

O MVP 0.1 é a soma das Fases 1 a 8. **A primeira etapa de desenvolvimento é somente a Fase 1.** Não iniciar o MVP inteiro simultaneamente.

## Fase 1 — Fundação (primeira etapa de desenvolvimento)

Objetivo: abrir uma estrutura navegável e acessível, aplicar temas e confirmar que a base local persiste dados com segurança. Ainda sem telas completas de criação de projetos, tarefas ou notas.

| Tarefa | Depende de | Resultado / critério de aceitação |
| --- | --- | --- |
| [ ] F01 — Inicializar projeto JavaScript com Vite | — | Package/lockfile, scripts de desenvolvimento e build, versão de Node suportada documentada e porta local estável; servidor não troca silenciosamente de porta |
| [ ] F02 — Criar layout principal responsivo | F01 | Menu recolhível, cabeçalho, região principal e gaveta móvel; apenas rotas do MVP visíveis; navegação a 360 px sem rolagem horizontal |
| [ ] F03 — Criar roteador e ciclo de vida das telas | F02 | Hash routes, import dinâmico, voltar/avançar, rota desconhecida e desmontagem; telas iniciais vazias identificam claramente seu estado |
| [ ] F04 — Criar tokens visuais e serviço de preferências | F02 | Tema claro/escuro/sistema, reação à mudança do SO, preferência persistida, fontes locais e aplicação do tema antes da renderização principal |
| [ ] F05 — Criar componentes compartilhados mínimos | F02, F04 | Campo rotulado, diálogo com foco, feedback, vazio e erro; funcionamento por teclado e foco visível |
| [ ] F06 — Definir modelos e validadores de entrada | F01 | Contratos de Project, Task, Note, Activity, SearchEntry e AppMeta; UUID, limites, enums, revision, datas civis e UTC separados |
| [ ] F07 — Criar banco, schema e migração inicial | F06 | Stores e índices apenas da 0.1; abertura/versionamento; tratamento de blocked/versionchange; nenhum reset automático |
| [ ] F08 — Criar unidade de transação e erros tipados | F07 | Commit confirma sucesso; aborto reverte conjunto de alterações; quota, conflito e indisponibilidade podem ser apresentados pela interface |
| [ ] F09 — Criar contratos e primitivas de repositório | F08 | Leitura por ID, escrita com revisão esperada e paginação por cursor; nenhum acesso direto a IndexedDB nas views |
| [ ] F10 — Conectar estado de persistência ao layout | F03, F05, F09 | Inicialização, banco indisponível, tentativa novamente, indicação de dados locais, revisão global e invalidação entre abas/foco |
| [ ] F11 — Verificar persistência e transações no navegador | F04, F10 | Cenários de registro sintético após reload, rollback, conflito entre abas e abertura bloqueada; fixtures isoladas da base pessoal |
| [ ] F12 — Validar a fundação e documentar execução | F11 | Build abre, navegação/tema/teclado/mobile revisados; README explica execução, origem estável, dados locais e limitações |

### Dependências da primeira etapa

```text
F01 -> F02 -> F03 ------------------------------+
        |                                      |
        +-> F04 -> F05 -------------------------+-> F10 -> F11 -> F12
                                               |           ^
F01 -> F06 -> F07 -> F08 -> F09 -----------------+           |
                          F04 -----------------------------+
```

### Entrega verificável da primeira etapa

A aplicação abre na mesma origem local, tem layout claro/escuro/sistema e navegação funcional. A camada de persistência é comprovada por um fluxo de teste com dados sintéticos: gravar, recarregar, ler, editar com revisão e provocar uma transação abortada sem mudança parcial.

O teste fica em ambiente isolado; o usuário não recebe projetos e notas de demonstração misturados à sua base. Não há CRUD de negócio, Dashboard preenchido, backup ou busca completa ainda. A primeira fase prepara essas funcionalidades; não deve ser apresentada como MVP pronto.

**Parar no gate F12 para revisar a fundação antes de iniciar a Fase 2.** Este é um marco técnico de revisão do incremento, sem acrescentar uma exigência de autorização além do escopo que o usuário definir na próxima solicitação.

## Fase 2 — Escritas consistentes e Projetos

Objetivo: criar, editar, listar, arquivar e excluir projetos, com dados confiáveis e base comum para busca e atividade recente.

| Tarefa | Depende de | Resultado / critério de aceitação |
| --- | --- | --- |
| [ ] P01 — Criar fábrica e repositório de atividades | F12 | Eventos pequenos com tipos estáveis e paginação; escrita só participa da transação do caso de uso |
| [ ] P02 — Criar normalização e projeção de busca | F12 | Normalização de caixa/acentos/espaços e projeção por tipo/ID; ainda sem diálogo de busca |
| [ ] P03 — Implementar regras e serviço de projetos | P01, P02 | Criar/editar com validação, revisão, projeção de busca e Activity atômicas; atualizar lastActivityAt |
| [ ] P04 — Criar listagem e filtros de projetos | P03 | Filtro por status, ordenação estável, paginação e estados vazio/erro |
| [ ] P05 — Criar formulários de criação e edição | P03, F05 | Nome, descrição, cor, ícone, status e prazo; erro não apaga formulário; navegação protege alterações não salvas |
| [ ] P06 — Criar página individual de projeto | P04, P05 | Visão geral por ID, edição e contexto do projeto; conteúdo relacionado vazio sem dados fictícios |
| [ ] P07 — Implementar arquivamento e exclusão | P06 | Arquivar preserva vínculos; excluir mostra impacto e preserva tarefas/notas sem projeto atomicamente |
| [ ] P08 — Validar fluxo de projetos | P07 | Criar, recarregar, editar, arquivar e excluir; testar rollback do conjunto projeto/busca/atividade e preservação de vínculos sintéticos |

Saída: o usuário consegue manter seus projetos. Progresso e próxima tarefa entram com as tarefas na fase seguinte; não inventar percentuais nesta fase.

## Fase 3 — Tarefas

Objetivo: organizar o trabalho diário e relacioná-lo aos projetos, com regras claras de prazo e conclusão.

| Tarefa | Depende de | Resultado / critério de aceitação |
| --- | --- | --- |
| [ ] T01 — Implementar regras de tarefa e datas | P08 | Prioridade/status, hoje/atrasada/próxima, conclusão/reabertura e contador de adiamento; testar virada de dia e prazo sem UTC indevido |
| [ ] T02 — Implementar serviço e consultas de tarefas | T01 | CRUD transacional atualiza busca, Activity e projetos afetados; valida projectId e revisão; suporta itens sem prazo/projeto |
| [ ] T03 — Criar lista e filtros de tarefas | T02 | Hoje, próximas, atrasadas, concluídas, todas, por projeto, prioridade e tags; páginas limitadas e ordenação previsível |
| [ ] T04 — Criar formulário de tarefa | T02 | Título, descrição, projeto, prioridade, prazo e tags; confirmação de exclusão e proteção de edição pendente |
| [ ] T05 — Adicionar subtarefas simples | T04 | Criar/editar/concluir/remover subtarefas com IDs estáveis, sem hierarquia recursiva |
| [ ] T06 — Conectar conclusão, reabertura e adiamento | T03, T05 | Ações refletem persistência confirmada; completedAt e contador seguem regras; falhas restauram o estado visual correto |
| [ ] T07 — Integrar tarefas à página do projeto | T06, P06 | Lista filtrada e criação com projeto preenchido; progresso derivado, próxima tarefa e “Sem tarefas” |
| [ ] T08 — Validar fluxo de tarefas | T07 | Conclusão/reabertura após reload; mudança de projeto; exclusão do projeto preserva tarefas; subtarefas e filtros corretos |

Definições: Hoje contém tarefas não concluídas com prazo no dia atual; atrasadas têm prazo anterior; próximas têm prazo futuro; Todas inclui sem prazo. Mostrar atrasadas junto de Hoje no Dashboard, mas manter os filtros distinguíveis. Tarefas concluídas saem dos filtros pendentes.

## Fase 4 — Notas estruturadas

Objetivo: guardar conhecimento em texto e recuperá-lo por título, conteúdo, projeto e tags.

| Tarefa | Depende de | Resultado / critério de aceitação |
| --- | --- | --- |
| [ ] N01 — Implementar serviço e consultas de notas | T08 | CRUD com validação, vínculo opcional, busca/atividade atômicas e revisão esperada |
| [ ] N02 — Criar lista de notas e filtros | N01 | Paginação, filtros por projeto/tags e ordenação por atualização; abrir nota por ID |
| [ ] N03 — Criar editor textual com salvamento explícito | N02 | Título, texto, formato plain/markdown, tags e projeto; indicação de alterações e proteção ao sair |
| [ ] N04 — Integrar notas à página do projeto | N03 | Aba Notas filtra por projeto e cria nota vinculada sem duplicar conteúdo |
| [ ] N05 — Validar notas e conflitos | N04 | Texto persiste após reload; conteúdo com HTML aparece como texto; outra aba não sobrescreve rascunho; exclusão de projeto preserva notas |

Saída: notas úteis sem editor de blocos. Pastas, categorias, imagens, preview de Markdown e anexos ficam nas etapas indicadas na arquitetura.

## Fase 5 — Busca global básica

Objetivo: encontrar rapidamente um projeto, tarefa ou nota sem navegar por várias páginas.

| Tarefa | Depende de | Resultado / critério de aceitação |
| --- | --- | --- |
| [ ] S01 — Criar consulta em lotes e ranqueamento | N05, P02 | Termos normalizados, todos os termos presentes, prioridade de título/tags/corpo, máximo de 50 resultados e progresso parcial explícito |
| [ ] S02 — Criar diálogo de busca e atalhos | S01 | Ctrl+K/Cmd+K e botão, foco inicial, setas/Enter/Escape e retorno de foco; tipos identificados |
| [ ] S03 — Adicionar debounce e cancelamento lógico | S02 | Consultas obsoletas não substituem resultado atual; fechar diálogo interrompe varredura; início não carrega todas as notas |
| [ ] S04 — Conectar resultados às rotas e busca de notas | S03 | Resultado abre o item correto; filtro de notas reutiliza a consulta por tipo; item removido é tratado |
| [ ] S05 — Validar consistência e medir busca | S04 | Criar/editar/excluir altera resultados; fixture de 5 mil itens respeita metas ou gera correção do índice antes do gate final |

Saída: busca textual previsível. Nenhum PDF é extraído ou indexado nesta fase. Se a busca linear não atingir a meta documentada, uma tarefa de índice invertido deverá preceder o gate V03, mantendo o mesmo contrato.

## Fase 6 — Dashboard utilizável

Objetivo: responder “o que preciso acompanhar agora?” com informações locais reais.

| Tarefa | Depende de | Resultado / critério de aceitação |
| --- | --- | --- |
| [ ] D01 — Criar consultas agregadas limitadas | S05 | Até 10 tarefas, 6 projetos e 10 atividades; obter contagens sem carregar registros completos desnecessários |
| [ ] D02 — Montar Hoje, atrasadas e projetos ativos | D01 | Prazos, progresso, próxima tarefa e última atividade; atalhos abrem listas filtradas |
| [ ] D03 — Implementar alertas por regras | D02 | Prazo hoje/amanhã, projeto ativo parado ≥7 dias e tarefa adiada ≥3 vezes; até 3 alertas com acesso ao contexto |
| [ ] D04 — Adicionar atividade recente e estados vazios | D03 | Eventos confirmados, sem cada clique; ações para criar primeiro item; nenhuma métrica fictícia |
| [ ] D05 — Validar atualização do Dashboard | D04 | Salvar/concluir/reabrir altera somente áreas afetadas; reload e retomada de foco refletem a base; virada de dia recalcula grupos |

Saída: Dashboard útil com os módulos entregues. Compromissos, biblioteca, favoritos e revisão não aparecem como funcionalidades disponíveis.

## Fase 7 — Backup e restauração

Objetivo: permitir retirar os dados do navegador e recuperá-los sem substituições silenciosas.

| Tarefa | Depende de | Resultado / critério de aceitação |
| --- | --- | --- |
| [ ] B01 — Definir formato versionado e validador de backup | D05 | Identificador, versões, metadados e coleções; rejeitar IDs/refs inválidos, enums, campos e tamanhos indevidos |
| [ ] B02 — Implementar exportação consistente | B01 | Snapshot único de IndexedDB e download JSON; excluir busca derivada e estado interno; conteúdo legível comunicado; mesmo limite de bytes do importador |
| [ ] B03 — Implementar análise e prévia de importação | B02 | Verificar limite antes de parse, apresentar novos/iguais/conflitos/erros sem escrever na base |
| [ ] B04 — Implementar mesclagem e conflito explícito | B03 | Preservar local por padrão, permitir escolha do backup, não duplicar IDs, validar referências após as escolhas |
| [ ] B05 — Implementar substituição transacional | B04 | Confirmação específica, oferta de exportação anterior, revisão da base conferida e rollback integral; nunca apagar antes de validar |
| [ ] B06 — Conectar Configurações e diagnóstico | B05 | Mesclar/Substituir/Cancelar, última exportação, uso estimado quando disponível, persistência opcional e explicação sobre origem/dispositivo |
| [ ] B07 — Verificar restauração e cenários de falha | B06 | Round-trip inclusive próximo ao limite de tamanho, merge repetido idempotente, conflitos, versão desconhecida, arquivo truncado, refs inválidas e alteração concorrente preservam dados |

Saída: um backup exportado restaura os mesmos dados canônicos em base limpa. Falha ou cancelamento não causa alteração parcial. Metadados derivados são reconstruídos e telas abertas são invalidadas após commit.

## Fase 8 — Gate de entrega do MVP 0.1

| Tarefa | Depende de | Resultado / critério de aceitação |
| --- | --- | --- |
| [ ] V01 — Executar fluxo completo de uso diário | B07 | Criar projeto → tarefas → conclusão → nota → busca → Dashboard → backup → restaurar; dados continuam corretos após reiniciar browser |
| [ ] V02 — Revisar acessibilidade, temas e responsividade | V01 | Teclado, foco/diálogos, contraste, menu móvel, formulários a 360 px e layout desktop; erros compreensíveis |
| [ ] V03 — Medir tamanho, consultas, memória e latência | V02 | Registrar ambiente e resultado com 5 mil/20 mil itens sintéticos; cumprir metas ou corrigir gargalos concretos antes de liberar |
| [ ] V04 — Verificar build de produção e operação local | V03 | Chrome/Edge e Firefox; assets locais; CRUD sem internet com servidor local ativo; não afirmar reabertura offline de PWA ainda |
| [ ] V05 — Atualizar documentação e marcar entrega 0.1 | V04 | Como executar, origem estável, backup/restauração, limites, dados locais e funções efetivamente entregues documentados |

MVP pronto significa todos os gates acima satisfeitos, não apenas telas visualmente completas. Nenhuma informação pessoal deve ir para fixtures, logs de teste, screenshots de demonstração ou repositório.

## Versão 0.2 — Biblioteca, PDFs e leituras

Estas tarefas começam somente depois de V05. O backup com arquivos é requisito da versão, não trabalho opcional para depois.

| Tarefa | Depende de | Resultado / critério de aceitação |
| --- | --- | --- |
| [ ] L01 — Migrar stores de arquivos e estado de leitura | V05 | FileRecord/FileBlob/PDFDocument/ReadingItem separados; consultas de metadados não carregam bytes |
| [ ] L02 — Importar arquivos com validação e quota | L01 | Formatos permitidos, limite inicial documentado, cópia local atômica e falha sem arquivo órfão |
| [ ] L03 — Criar listagem, filtros e previews seguros | L02 | Nome/tipo/tamanho/data/tags/projeto, busca e ordenação; texto/código nunca executado; URLs temporárias liberadas |
| [ ] L04 — Criar organização por pastas e categorias | L03 | Folder com parentId sem ciclos; Category e vínculo de notas; migração não perde tags/projetos existentes |
| [ ] L05 — Empacotar PDF.js e worker sob demanda | L03 | Versões compatíveis, assets locais necessários e nenhum PDF.js no carregamento inicial |
| [ ] L06 — Criar navegação, zoom e camada textual de PDF | L05 | Página/total, anterior/próxima, ir à página, ampliar/reduzir e tela cheia; render antigo cancelado |
| [ ] L07 — Criar busca no PDF e retomada | L06 | Busca progressiva cancelável, PDF sem texto informado, estado persistido e continuar da última página |
| [ ] L08 — Criar lista de leituras | L07 | PDFs em andamento, posição/progresso/última leitura derivados da fonte correta; abrir leitor no ponto salvo |
| [ ] L09 — Estender busca global para metadados de arquivos | L03, S05 | Nomes, tags e projeto pesquisáveis sem extrair todos os PDFs |
| [ ] L10 — Definir pacote de backup com binários | L02, B07 | Escolher ZIP/libraria após medir, manifesto versionado, limites descompactados e estratégia de importação segura |
| [ ] L11 — Implementar exportação/restauração de arquivos | L10 | Pacote inclui bytes; integridade, falha e cancelamento verificados; JSON só de metadados claramente identificado |
| [ ] L12 — Validar biblioteca e liberar 0.2 | L04, L08, L09, L11 | PDF real, imagem, código, senha/arquivo inválido, exclusões com integridade, retomada após reload e restauração dos bytes |

Favoritos de arquivos passam a funcionar quando a infraestrutura única de favoritos entrar na 0.4. Anotações associadas a páginas ficam planejadas para depois do leitor básico, sem impedir a entrega 0.2.

## Versão 0.3 — Quadros / Notas Flutuantes

| Tarefa | Depende de | Resultado / critério de aceitação |
| --- | --- | --- |
| [ ] Q01 — Inspecionar Notas Flutuantes original se disponível | L12 | Registrar o que é reutilizável e o formato de importação; se indisponível, documentar e manter desenvolvimento independente |
| [ ] Q02 — Criar modelos, migração e múltiplos quadros | Q01 | Board/BoardNote com IDs estáveis e vínculo opcional com projeto; CRUD com busca e backup atualizados |
| [ ] Q03 — Criar captura e edição simples de nota | Q02 | Abrir → escrever; editar/excluir/cor sem formulário excessivo; links seguros |
| [ ] Q04 — Implementar coordenadas, movimento e redimensionamento | Q03 | Pointer Events, pinagem, persistência ao fim do gesto e posição correta após reload |
| [ ] Q05 — Implementar zoom e pan | Q04 | Conversão mundo/tela, limites de zoom, foco preservado e seleção de texto sem conflito com pan |
| [ ] Q06 — Implementar desfazer/refazer por comandos | Q05 | Criar/editar/mover/redimensionar/excluir podem ser revertidos; limite de memória e tratamento de conflito entre abas |
| [ ] Q07 — Adicionar imagens/anexos e busca no quadro | Q06 | Referenciar FileRecord, centralizar item encontrado e integrar busca global; manter simplicidade visual |
| [ ] Q08 — Validar quadros e liberar 0.3 | Q07 | Dois quadros independentes, projeto vinculado, backup/restauração e movimento fluido; mobile oferece consulta/edição simples |

Não migrar automaticamente nem alterar a base do projeto original. Importador, se viável e solicitado, recebe tarefa própria após a inspeção.

## Versão 0.4 — Organização complementar

| Tarefa | Depende de | Resultado / critério de aceitação |
| --- | --- | --- |
| [ ] O01 — Adicionar schema das entidades complementares | Q08 | Event, Link, Favorite e InboxItem; migração e backup refletem o formato entregue |
| [ ] O02 — Implementar biblioteca de links | O01 | URL validada, título/descrição/tags/projeto, pesquisa; sem fetch remoto automático de favicon |
| [ ] O03 — Implementar captura no Inbox | O01 | Texto salvo com mínimo de interação; lista e estado de item convertido preservados |
| [ ] O04 — Implementar conversão de Inbox | O02, O03 | Criar tarefa/nota/projeto/link/leitura e marcar captura na mesma transação; erro não perde o original |
| [ ] O05 — Implementar favoritos transversais | O02 | Store único por tipo/ID, atalhos no menu/busca e limpeza de vínculo ao excluir entidade |
| [ ] O06 — Criar eventos e consulta unificada do calendário | O01 | Eventos próprios mais prazos existentes, sem duplicar tarefas ou projetos; fuso e eventos de dia inteiro corretos |
| [ ] O07 — Criar mês, semana e próximos eventos | O06 | Navegação temporal e abertura da origem; lembretes ao abrir app sem promessa de notificação com app fechado |
| [ ] O08 — Criar página de histórico | O01 | Paginação/filtros por período, projeto e tipo usando Activity existente; itens removidos continuam legíveis |
| [ ] O09 — Integrar Dashboard e páginas de projeto | O04, O05, O07, O08 | Compromissos e links reais, histórico contextual e atalhos úteis sem sobrecarregar o Dashboard |
| [ ] O10 — Validar módulos e liberar 0.4 | O09 | Conversão atômica/idempotente, favoritos sem órfãos, calendário correto e round-trip do backup ampliado |

## Versão 0.5 — Revisão semanal e PWA completa

| Tarefa | Depende de | Resultado / critério de aceitação |
| --- | --- | --- |
| [ ] W01 — Definir e implementar agregações semanais | O10 | Limites de semana no fuso correto, conclusões distintas, projetos atualizados/parados, adiamentos, arquivos e dias ativos |
| [ ] W02 — Criar página de revisão | W01 | Escolher semana e abrir itens de origem; métricas reproduzíveis e sem IA ou tempo fictício |
| [ ] W03 — Criar manifest e assets de instalação | O10 | Nome, escopo, início, display e ícones; estados de instalação variam por suporte do navegador |
| [ ] W04 — Implementar cache versionado do build | W03 | Shell, módulos entregues e assets do PDF disponíveis offline após instalação concluída; nenhum Blob pessoal duplicado no cache |
| [ ] W05 — Implementar atualização coordenada | W04 | Atualização aguarda edições salvas, coordena abas/banco e preserva versão anterior até ativação segura |
| [ ] W06 — Testar reinício offline e upgrade | W05 | Fechar/reabrir browser sem rede, navegar em todas as rotas, abrir PDF local e migrar entre duas builds sem perda |
| [ ] W07 — Validar revisão/PWA e liberar 0.5 | W02, W06 | Relatórios verificáveis, instalação onde suportada, backup restaurável e manual de recuperação atualizado |

## Futuro — somente após necessidade demonstrada

| Candidato | Pré-condição | Decisão exigida antes de implementar |
| --- | --- | --- |
| Anotações por página de PDF | L12 | UX de Note.pdfFileId/pdfPage, integridade ao excluir arquivo e abertura na página vinculada |
| Tags como entidades próprias | Uso real de tags simples | Necessidade de cor/renomeação global; migração sem duplicar labels e referências |
| Sincronização/Supabase | W07 e pedido concreto de múltiplos dispositivos | Identidade, autenticação, tombstones, conflitos, arquivos, quota, retries e modelo de permissão |
| Gmail/Calendar/Drive/GitHub/webhooks | Integração específica solicitada | Escopos mínimos, revogação, dados transmitidos e limites de API |
| Assistente opcional | Fluxo útil identificado | Consentimento por conteúdo, custo, provedor e funcionamento integral sem chave/API |
| Pesquisa global no texto de PDFs/OCR | Busca por metadados insuficiente | Custo de CPU, armazenamento, atualização/cancelamento e limite de documentos |

Esses candidatos não bloqueiam nenhuma versão anterior e não justificam criar serviços vazios agora.

## Política de verificação

Testar regras de maior risco: datas, adiamentos, transações, integridade de relações, conflitos de edição, migrações e backup. Preferir o navegador real para IndexedDB; mocks sozinhos não comprovam comportamento transacional.

Verificações visuais e de teclado cobrem layout, temas, foco, estados vazios e erros. Não criar testes que apenas repetem a implementação de um componente simples. Usar fixtures sintéticas e banco/origem isolados; nunca limpar o banco do usuário para rodar testes.

Após checks adequados passarem, avançar para a próxima tarefa. Repetir ou ampliar testes quando houver mudança, falha ou preocupação concreta pendente. Registrar limitações em vez de marcar uma tarefa incompleta como entregue.

## Ponto de parada atual

Entregues: arquitetura, plano, código do MVP, integração do Notas Flutuantes, instruções de execução e relatório de verificação. O ponto de parada original antes da implementação foi superado pela autorização posterior do usuário.

Próximos incrementos devem partir do código existente e das limitações documentadas, preservando o compartilhamento da fonte do Notas Flutuantes. Biblioteca/PDF próprios, calendário unificado, Inbox, favoritos, revisão semanal e PWA completa continuam fora desta versão.
