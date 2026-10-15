# Painel Pessoal — arquitetura e escopo

Data: 19/09/2026. Estado: arquitetura de referência; MVP 0.1 implementado em solicitação posterior.

Este documento registra as decisões do planejamento inicial, quando a pasta ainda estava vazia. A solicitação posterior autorizou a implementação e o acesso à pasta irmã `notas-flutuantes`. O estado executável está descrito em [README.md](README.md) e as verificações em [VERIFICATION.md](VERIFICATION.md).

**Ajuste de escopo solicitado pelo usuário:** Quadros foi antecipado usando o aplicativo original, isolado visualmente por iframe da mesma origem. Uma junction em `integrations/notas-flutuantes` compartilha a fonte; o adaptador do Vite serve os arquivos em desenvolvimento e os copia para distribuição. O store adicional `boardLinks` relaciona quadros a projetos. O armazenamento e o backup internos do Notas Flutuantes permanecem independentes; não foram substituídos pelo modelo futuro Board/BoardNote deste documento.

**Primeira entrega de produto: MVP 0.1.** Inclui estrutura visual, Dashboard, Projetos, Tarefas, Notas, busca básica, IndexedDB, temas e backup. Os demais módulos têm contratos e lugar no roadmap, mas não devem ser construídos agora. As tarefas estão em [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 1. Visão geral da arquitetura

Aplicação estática, local-first, de um usuário por perfil do navegador. O navegador executa a interface e mantém os dados. Não haverá backend obrigatório, login, telemetria, chamadas de IA ou dependência de internet para operações locais.

```text
Interface: layout + rotas + componentes acessíveis
                         |
Módulos: dashboard, projetos, tarefas, notas, busca, configurações
                         |
Serviços de aplicação: validar, coordenar mudanças, aplicar regras
                         |
Contratos de repositório + unidade de transação
                         |
Adaptador IndexedDB: registros, índices e migrações

Após a confirmação da transação -> notificação -> atualizar views afetadas
```

As telas não chamam IndexedDB diretamente. Repositórios conhecem persistência; serviços conhecem regras; componentes conhecem apresentação. Dashboard e busca consultam vários repositórios sem importar telas de outros módulos.

Uma edição grava a entidade afetada e seus efeitos relacionados em uma transação. Não se salva um objeto gigante contendo toda a aplicação. Estado de formulário e seleção fica na tela; preferências pequenas ficam em localStorage; dados pessoais ficam em IndexedDB.

Cada módulo expõe registro de rota, montagem e desmontagem da tela. Desmontar remove listeners, observadores, tarefas pendentes e recursos temporários. Importações dinâmicas carregam a tela quando necessário. Haverá um registro explícito de módulos, sem criar um sistema genérico de plugins.

No futuro, sincronização será um serviço adicional que conversa com o repositório local. Um adaptador remoto precisará de protocolo para conflitos, exclusões e falhas; substituir IndexedDB por Supabase não resolve isso sozinho. Os contratos evitam reescrever a interface, mas não prometem sincronização gratuita.

## 2. Tecnologias recomendadas

| Camada | Escolha | Quando |
| --- | --- | --- |
| Interface | HTML semântico, CSS e JavaScript nativo com módulos ES | 0.1 |
| Organização de código | JSDoc nos modelos e contratos; funções e módulos pequenos | 0.1 |
| Desenvolvimento/build | Node.js em versão LTS suportada + Vite, somente ferramentas | 0.1 |
| Persistência | API nativa IndexedDB, encapsulada em um adaptador pequeno | 0.1 |
| Preferências | localStorage e `matchMedia` | 0.1 |
| Roteamento | Rotas por hash e tabela explícita de rotas | 0.1 |
| Interface gráfica | CSS Grid/Flexbox, fontes do sistema e poucos SVGs locais | 0.1 |
| Verificação | `node:test` para regras; Playwright como dependência de desenvolvimento para fluxos no navegador | 0.1 |
| Arquivos | File/Blob, IndexedDB e URLs temporárias de objetos | 0.2 |
| PDF | PDF.js distribuído junto com a aplicação, carregado sob demanda | 0.2 |
| Instalação/offline completo | Web App Manifest, Service Worker e Cache Storage | 0.5 |

As versões exatas serão verificadas e fixadas no lockfile na implementação. O navegador do usuário não precisará de Node.js instalado quando acessar uma distribuição hospedada.

## 3. Justificativas e limites das escolhas

JavaScript nativo basta para formulários, listas paginadas e páginas independentes. Evita um framework e um gerenciador de estado antes de existir necessidade. JSDoc documenta contratos sem acrescentar compilação de tipos obrigatória; checagem estática adicional poderá ser avaliada quando houver código que a justifique.

Vite oferece servidor local e build estático com suporte a importações dinâmicas. É uma dependência de desenvolvimento: não um framework carregado pela aplicação. A recomendação usa esses recursos descritos na [documentação oficial do Vite](https://vite.dev/guide/). Não adicionar plugins sem um problema concreto.

IndexedDB suporta registros estruturados, índices e transações assíncronas, adequados para dados locais. O adaptador deverá centralizar os cuidados com a API; se ele crescer desproporcionalmente, reavaliar uma biblioteca pequena, sem trocar a interface dos repositórios. [Referência técnica: conceitos de IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API/Basic_Terminology).

Rotas por hash permitem hospedagem estática sem regras de reescrita e permitem abrir diretamente um projeto ou uma nota. Não há necessidade de SSR ou SEO neste painel pessoal. CSS próprio com tokens basta; não utilizar biblioteca de componentes, pacote grande de ícones ou fontes remotas.

PDF.js entra apenas quando houver PDFs. Um visualizador nativo em iframe não oferece controle portátil suficiente sobre página atual, busca e retomada. Ferramentas de teste ficam fora do bundle de produção.

Alvo inicial de validação: Chrome/Edge e Firefox estáveis em desktop; telas essenciais também em navegador móvel. Instalação e APIs opcionais dependem do navegador e devem ser detectadas. Não prometer suporte a navegadores antigos ou instalação idêntica em todas as plataformas.

## 4. Estrutura de diretórios proposta

Árvore de destino, não uma solicitação para criar pastas vazias. Cada diretório nasce junto com sua primeira responsabilidade.

```text
organizador/
  ARCHITECTURE.md
  IMPLEMENTATION_PLAN.md
  README.md                       # execução, backup e limitações; na implementação
  index.html
  package.json
  public/
    icons/
    manifest.webmanifest          # 0.5
  src/
    main.js
    app/
      bootstrap.js
      router.js
      routes.js
      shell.js
    components/
      dialog.js
      form-field.js
      empty-state.js
      pagination.js
      feedback.js
    domain/
      models.js                   # contratos JSDoc
      validation.js
      task-rules.js
      project-rules.js
    modules/
      dashboard/
      projects/
      tasks/
      notes/
      search/
      settings/
      library/                    # 0.2 em diante
      pdf/
      readings/
      boards/                     # 0.3
      calendar/                   # 0.4
      inbox/
      links/
      favorites/
      history/
      review/                     # 0.5
    services/
      project-service.js
      task-service.js
      note-service.js
      dashboard-service.js
      search-service.js
      activity-service.js
      backup-service.js
      preferences-service.js
      change-notifier.js
    storage/
      contracts.js
      indexeddb/
        database.js
        migrations.js
        transactions.js
        project-repository.js
        task-repository.js
        note-repository.js
        activity-repository.js
        search-repository.js
        meta-repository.js
    utils/
      dates.js
      ids.js
      text.js
      debounce.js
    styles/
      tokens.css
      base.css
      layout.css
      components.css
    sw.js                         # 0.5; build trata sua distribuição
  tests/
    unit/
    browser/
    fixtures/                     # dados sintéticos, nunca dados pessoais
```

Uma view pode manter seus componentes específicos dentro do módulo. Só mover para `components/` aquilo que já for compartilhado. Contratos não exigem hierarquias de classes nem um repositório genérico com dezenas de opções.

## 5. Módulos, responsabilidades e fronteiras

| Módulo | Responsabilidade | Entrega |
| --- | --- | --- |
| Dashboard | Hoje, atrasadas, projetos ativos, próximas tarefas, atividade recente e alertas simples | 0.1 |
| Projetos | CRUD, status e página com visão geral, tarefas e notas relacionadas | 0.1 |
| Tarefas | CRUD, conclusão/reabertura, prioridade, prazo, tags, subtarefas e filtros | 0.1 |
| Notas | Título, texto, tags, vínculo com projeto e pesquisa | 0.1 |
| Busca | Pesquisar projetos, tarefas e notas por um diálogo global | 0.1 |
| Configurações | Tema, transparência sobre dados locais e backup | 0.1 |
| Biblioteca | Metadados de arquivos, importação local, filtros e visualização | 0.2 |
| PDF/Leituras | Leitor, retomada e lista de leituras de arquivos | 0.2 |
| Quadros | Notas Flutuantes livres, múltiplos quadros e relação com projeto | 0.3 |
| Calendário | Mês, semana e agenda unindo tarefas, projetos e eventos | 0.4 |
| Inbox | Captura rápida e conversão explícita para entidades | 0.4 |
| Links/Favoritos | Links organizados e atalhos para entidades | 0.4 |
| Histórico | Consulta e filtros sobre as atividades já registradas | 0.4 |
| Revisão semanal | Agregações de dados locais, sem IA | 0.5 |

No MVP, não exibir botões desabilitados para todos os módulos futuros. A navegação contém Início, Tarefas, Projetos, Notas, Busca e Configurações. A busca também tem botão no cabeçalho e `Ctrl+K`/`Cmd+K`.

Notas estruturadas inicialmente usam editor de texto simples, adequado a parágrafos, listas, código e Markdown como texto. Não há editor de blocos, preview HTML, imagens ou anexos no MVP. Pastas e categorias entram com a evolução da organização em 0.2. A primeira versão ainda permite organização por projeto e tags.

O Dashboard 0.1 não inventa compromissos, leituras ou estatísticas de arquivos. Mostra apenas informações existentes. As abas Arquivos, Links e Histórico da página de projeto surgem nas versões correspondentes.

## 6. Modelos de dados

### Convenções

Entidades editáveis possuem `id` UUID estável, `createdAt`, `updatedAt` e `revision` inteiro. Datas de registro são instantes ISO 8601 em UTC. Prazos de dia inteiro usam `YYYY-MM-DD` no calendário local, sem conversão implícita para meia-noite UTC. Ausência de prazo ou vínculo usa `null`.

`revision` aumenta a cada gravação confirmada e detecta edições concorrentes na mesma base. Não é um relógio distribuído nem decide conflitos de backup. Textos têm limites explícitos, definidos por contrato: título até 200 caracteres, descrição até 10 mil, corpo de nota até 200 mil, até 30 tags de 40 caracteres e até 100 subtarefas por tarefa. São limites iniciais ajustáveis, para impedir registros acidentais gigantes.

Tags no MVP são valores normalizados em listas, sem coleção própria: trim, caixa uniforme e deduplicação. Não criar IDs e tabelas para simples rótulos. Se houver nomes editáveis, cores e hierarquia de tags no futuro, uma migração introduz `Tag` e substitui os valores por referências.

### Modelos da versão 0.1

| Entidade | Campos específicos | Regras |
| --- | --- | --- |
| Project | `name`, `description`, `icon`, `color`, `status`, `dueDate`, `lastActivityAt` | Status: planning, active, paused, completed, archived; labels em português |
| Task | `title`, `description`, `projectId`, `priority`, `dueDate`, `tags[]`, `status`, `subtasks[]`, `completedAt`, `postponementCount` | Prioridade: low, normal, high, urgent; status: pending, in_progress, completed |
| Subtask | `id`, `title`, `completed` | Valor embutido na tarefa; não é tarefa recursiva nem tem projeto próprio |
| Note | `title`, `body`, `format`, `projectId`, `tags[]` | `format`: plain ou markdown; edição textual no MVP |
| Activity | `id`, `type`, `entityType`, `entityId`, `projectId`, `label`, `occurredAt` | Registro imutável e pequeno; label permite histórico após exclusão |
| SearchEntry | `key`, `entityType`, `entityId`, `title`, `titleNormalized`, `tagsNormalized`, `textNormalized`, `updatedAt` | Projeção derivada, reconstruível; chave composta por tipo e ID |
| AppMeta | `key`, `value` | Versão de formato lógico, identidade da base, revisão global e informações de manutenção |

Progresso de projeto é `tarefas concluídas / total de tarefas × 100`, arredondado para exibição. Sem tarefas: “Sem tarefas”, sem percentual fictício. Não salvar `progress` duplicado. A próxima tarefa é a pendente com menor prazo; empates usam prioridade e data de criação. Tarefas sem prazo vêm depois das datadas.

`lastActivityAt` é uma projeção materializada: criação/edição do projeto ou mudança relevante em seus itens atualiza esse campo na mesma transação. Abrir uma página não atualiza o campo. É a exceção deliberada à duplicação para listar projetos sem varrer o histórico.

Concluir uma tarefa define `completedAt`; reabrir limpa esse valor e registra atividade. Adiamento significa mover um prazo já existente para um dia posterior: incrementa o contador uma vez por alteração confirmada. Definir o primeiro prazo, antecipar ou editar outro campo não conta como adiamento.

Status do projeto é independente do percentual de tarefas. Não concluir nem reabrir projetos automaticamente. Subtarefas ajudam a organizar a execução; completar todas não conclui a tarefa sem ação explícita.

### Modelos posteriores, sem criar stores antecipados

| Entidade | Campos específicos previstos | Versão |
| --- | --- | --- |
| FileRecord | `name`, `mimeType`, `size`, `blobId`, `projectId`, `tags[]`, `folderId` | 0.2 |
| FileBlob | `id`, `blob` | 0.2; conteúdo separado dos metadados |
| PDFDocument | `fileId`, `pageCount`, `lastPage`, `lastReadAt`, `zoom`, `rotation` | 0.2; chave `fileId`, relação 1:1 |
| ReadingItem | `sourceType`, `sourceId`, `status`, `lastReadAt` | 0.2; fonte arquivo, ampliada para link em 0.4 |
| Folder | `name`, `parentId`, `scope` | 0.2; scope notes ou files; impedir ciclos |
| Category | `name` | 0.2; notas recebem `categoryId` opcional |
| Board | `name`, `projectId`, `background` | 0.3 |
| BoardNote | `boardId`, `text`, `color`, `x`, `y`, `width`, `height`, `zIndex`, `pinned` | 0.3 |
| Attachment | `ownerType`, `ownerId`, `fileId` | 0.3; vínculo, não cópia do arquivo |
| Event | `title`, `description`, `projectId`, `startAt`, `endAt`, `timeZone`, `allDay`, `reminderAt` | 0.4; variante dia inteiro usa datas locais |
| Link | `url`, `title`, `description`, `tags[]`, `projectId` | 0.4 |
| Favorite | `id`, `entityType`, `entityId`, `createdAt` | 0.4; combinação tipo/ID única |
| InboxItem | `text`, `state`, `convertedToType`, `convertedToId` | 0.4 |
| Tag | `name`, `color` | Futuro, somente se rótulos simples forem insuficientes |

ReadingItem não duplica página e total de páginas: para PDFs, seu progresso e última leitura vêm de PDFDocument. Seu `lastReadAt` serve às fontes sem estado próprio, como artigos; não manter dois valores concorrentes para PDFs. Nenhuma outra entidade ganha `isFavorite`: Favorite é a fonte única.

Para anotações em PDF, reservar a evolução de Note com `pdfFileId` e `pdfPage` opcionais e validados em conjunto. A nota referencia o arquivo e sua página, sem modificar bytes do PDF. Implementação dessa associação fica posterior ao leitor básico.

## 7. Relações, integridade e exclusões

```text
Project 1 --- N Task
Project 1 --- N Note
Project 1 --- N FileRecord / Link / Board       [futuro]
Task    1 --- N Subtask                        [embutidas]
Board   1 --- N BoardNote                      [futuro]
FileRecord 1 --- 1 FileBlob                    [futuro]
FileRecord 1 --- 0..1 PDFDocument              [futuro]
Note N --- 0..1 FileRecord + página            [anotações futuras]
Attachment N --- 1 FileRecord                  [futuro]
Favorite N --- 1 entidade, por tipo e ID       [futuro]
Activity N --- 0..1 Project + referência histórica à entidade
```

Uma tarefa/nota pode estar sem projeto; um projeto pode conter zero itens. Não repetir o nome do projeto nas tarefas ou notas. A interface resolve nomes por IDs em consultas agrupadas. Activity guarda um rótulo histórico deliberadamente, não um vínculo usado para integridade atual.

IndexedDB não aplica chaves estrangeiras. Serviços e importador validam referências dentro da mesma unidade de alteração.

Excluir projeto mostra a quantidade de vínculos e exige confirmação. A regra inicial é preservar tarefas e notas, definindo `projectId = null`, e então excluir o projeto, tudo atomicamente. Não existe exclusão em cascata de conteúdo pessoal no MVP. Arquivar preserva todas as relações.

Excluir tarefa ou nota também pede confirmação. Busca derivada é removida na mesma transação. O histórico permanece e identifica o item como removido. Quando Favoritos existir, remover seus vínculos na mesma operação. Excluir um arquivo vinculado exigirá tratar os anexos e as anotações antes de remover seu Blob; não deixar referências quebradas.

Mudanças entre projetos atualizam a atividade dos projetos de origem e destino. A data de edição da entidade não muda apenas porque alguém a abriu. Filtros, consulta e navegação não geram alterações no conteúdo.

## 8. Estratégia de IndexedDB

### Banco, índices e consultas

Nome proposto: `painel-pessoal`. A versão física do banco é um inteiro próprio, independente da versão do produto e do formato de backup.

| Store inicial | Chave | Índices iniciais ligados a consultas reais |
| --- | --- | --- |
| projects | `id` | `status`, `updatedAt`, `lastActivityAt`, `dueDate` |
| tasks | `id` | `projectId`, `[status, dueDate]`, `[projectId, status]`, `completedAt`, `updatedAt`, `tags` multiEntry |
| notes | `id` | `projectId`, `updatedAt`, `tags` multiEntry |
| activities | `id` | `occurredAt`, `[projectId, occurredAt]`, `[type, occurredAt]` |
| searchEntries | `key` | `entityType` |
| meta | `key` | nenhum |

Valores `null` não produzem chaves úteis para índices de prazo. Consultas gerais e “sem prazo” precisam de caminho explícito pelo store ou índice de status/projeto, sem assumir que o índice por prazo inclui todos. Listas usam páginas de 50 e cursores com desempate pela chave primária; não usar deslocamentos crescentes como única paginação.

Contratos mínimos: obter por ID; listar por filtro com cursor; criar; atualizar com revisão esperada; excluir. Consultas especializadas cobrem contagens e prazos. Transações de aplicação permitem atualizar entidade, projeção de busca, projeto e Activity juntas, sem expor IDBTransaction às telas.

### Segurança das gravações

Resolver uma operação somente em `transaction.oncomplete`, nunca apenas no sucesso de um `put`. Validar e preparar dados antes de abrir a transação. Dentro dela, apenas operações IndexedDB encadeadas; não aguardar rede, temporizadores ou processamento externo que permita seu encerramento antecipado.

Falha de cota, transação abortada ou erro de abertura não pode aparecer como “Salvo”. Manter texto no formulário, permitir tentar novamente e oferecer diagnóstico. Não cair silenciosamente para memória ou localStorage se o banco falhar. O usuário deve saber quando os dados não estão persistidos.

Migrações de estrutura ocorrem em `onupgradeneeded` e são incrementais. Implementar `onblocked` com orientação para fechar/recarregar outra aba, e `versionchange` fechando a conexão antiga. Nunca apagar o banco automaticamente para corrigir uma migração. Essa coordenação é exigida pelo funcionamento da API, conforme [Using IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API/Using_IndexedDB).

Antes de migrações grandes, oferecer exportação e planejar transformação retomável. No MVP, as migrações devem ser pequenas e verificadas contra uma base de versão anterior de teste. Manter a versão anterior utilizável quando a atualização falhar.

### Abas, rascunhos e preferências

Toda gravação incrementa a revisão da base em `meta`. BroadcastChannel anuncia alterações já confirmadas; ao recuperar foco, a tela confere a revisão como fallback. Uma edição compara `revision` dentro da transação: se mudou, conservar o rascunho e mostrar o conflito, sem sobrescrever outra aba.

No MVP, formulários usam “Salvar” explícito. Ao sair de uma rota com alterações, oferecer salvar, descartar ou permanecer. `beforeunload` é proteção complementar, sem prometer recuperar uma aba encerrada à força. Autosave só entra depois de existir solução clara para rascunhos e conflitos.

localStorage guarda apenas tema (`light`, `dark`, `system`), menu recolhido e preferências pequenas de apresentação. Falha nesse armazenamento não impede abrir os dados. Nenhum título, corpo de nota, lista de tarefas ou arquivo fica nele.

### Quota e origem

Exibir em Configurações que os dados pertencem a este navegador/dispositivo. Consultar estimativas de armazenamento quando suportado e oferecer persistência pelo Storage API; a concessão não é garantida. Limpeza do navegador continua podendo apagar dados e backup externo continua necessário. [Referência: armazenamento e critérios de remoção](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria).

Manter origem estável, inclusive porta no ambiente local. Mudar protocolo, hostname ou porta exige exportar/importar: IndexedDB é isolado por origem. A pasta estar dentro do OneDrive não sincroniza o banco do navegador. [Referência: isolamento de IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API/Using_IndexedDB).

## 9. Armazenamento de arquivos — 0.2

Importar arquivo significa copiar seus bytes para o armazenamento local da aplicação. A referência não acompanha alterações no arquivo original. Explicar isso no fluxo de importação.

FileRecord guarda metadados leves; FileBlob guarda Blob. A listagem consulta apenas metadados. Gravar ambos atomicamente após validar formato e tamanho. Um limite inicial de 25 MiB por arquivo é proposta de produto a validar com PDFs reais, não limite do navegador. Avisar antes de importar lotes cujo tamanho exceda a margem estimada disponível; ainda tratar a falha real de quota.

Suporte inicial: PDF, TXT, Markdown, PNG/JPEG/WebP e pequenos arquivos de código/texto. HTML, SVG e código nunca são executados para preview. Mostrar texto com `textContent`, abrir imagens raster como imagens e verificar tipo/conteúdo quando necessário. Não carregar automaticamente imagens ou favicons remotos contidos nas notas e links.

Criar URLs de Blob apenas durante a visualização/download e revogá-las ao encerrar. Miniaturas são cache derivado limitado; não duplicar imagens completas. Não ler todos os Blobs no startup e não converter arquivos para base64 para armazenar no banco.

OPFS, acesso direto a pastas do computador, deduplicação por hash e arquivos enormes ficam fora da primeira biblioteca. O BlobRepository permite reavaliar o armazenamento depois de medir uso real.

## 10. Arquitetura do visualizador de PDF — 0.2

```text
Biblioteca -> rota pdf/:fileId?page=N -> PdfReaderController
                                      |-> FileRepository: Blob
                                      |-> PDF.js + worker local
                                      |-> visualização e camada de texto
                                      |-> PDFStateRepository: retomada
```

O pacote PDF.js e o worker entram num carregamento separado; worker e biblioteca usam a mesma versão. Assets auxiliares exigidos pela distribuição, como fontes e CMaps, também precisam ser empacotados localmente e incluídos na estratégia offline. Renderização e extração de texto seguem as APIs documentadas nos [exemplos oficiais de PDF.js](https://mozilla.github.io/pdf.js/examples/) e na [referência da biblioteca](https://mozilla.github.io/pdf.js/api/draft/module-pdfjsLib.html).

Primeiro leitor com uma página visível por vez, botões anterior/próxima, campo de página, total, zoom, ajuste à largura, busca e tela cheia quando disponível. Limitar dimensões de canvas e escala em telas de alta densidade; cancelar render anterior ao mudar rapidamente de página e liberar documentos/canvases ao sair.

Salvar a última página efetivamente exibida, com debounce, e tentar concluir a gravação ao mudar a página ou sair pela aplicação. Não depender exclusivamente de unload. Ao reabrir: “Continuar da página 37?” com opções Continuar e Início. Uma rota com página explícita prevalece sobre a retomada e será usada por anotações.

Pesquisa textual percorre páginas progressivamente, com cancelamento e indicador de andamento. Não extrair o livro inteiro na abertura. Cache de texto tem tamanho limitado. PDFs digitalizados sem texto mostram essa limitação; OCR fica fora do escopo.

PDFs inválidos, protegidos por senha, indisponíveis ou grandes demais precisam de estados próprios. Senha, quando solicitada, não é persistida. Desabilitar execução de JavaScript incorporado e validar links externos. PDFs não podem executar conteúdo arbitrário como parte da interface.

Leituras deriva percentual de `lastPage / pageCount`. Isso representa posição de leitura, não prova de páginas estudadas; não inventar métricas de tempo. Anotações por página serão notas relacionadas, sem editor de PDF, reconhecimento de escrita ou modificação do arquivo original.

## 11. Arquitetura de Notas Flutuantes / Quadros — 0.3

Manter o conceito **abrir → escrever → mover**. BoardNote não vira Task nem Note estruturada automaticamente. A interface oferece criação rápida e poucas ações visíveis; cor, pinagem e anexos ficam em menu contextual acessível por botão e teclado.

Implementar com elementos DOM posicionados num plano lógico, sem biblioteca gráfica grande. A câmera aplica translação e escala ao plano. Coordenadas persistidas são do mundo do quadro, não pixels da janela; pointer position é convertida pela transformação inversa. Usar Pointer Events, pointer capture e `requestAnimationFrame` para movimento.

Pan ocorre no fundo ou com gesto dedicado, sem competir com seleção de texto. Zoom tem limites e preserva o ponto de interesse. Ao mover/redimensionar, atualizar visualmente em memória e gravar somente no fim do gesto. Cada nota tem registro próprio. Pinagem impede movimento acidental e mantém edição do texto.

Desfazer/refazer usa comandos locais com estado anterior/posterior apenas dos itens afetados: criar, editar, mover, redimensionar, recolorir e excluir. Agrupar digitação numa operação; limitar pilha, por exemplo, a 50 comandos por quadro. Não é event sourcing, não usa Activity como pilha e não precisa sobreviver a recarregamento. Atualização concorrente de outra aba invalida comandos incompatíveis para não sobrescrever alterações.

Quadro tem nome e projeto opcional; BoardNote herda esse contexto pelo quadro. Imagens/anexos usam Attachment e FileRecord, sem bytes dentro da nota. Links são texto clicável com protocolo validado. Pesquisa filtra/encontra notas; seleção centraliza a câmera na nota.

Vários quadros são independentes. Em grande quantidade, renderizar apenas notas da região visível com margem; implementar essa otimização após medição. No celular, priorizar leitura/edição simples e uma alternativa em lista; manipulação espacial avançada continua otimizada para desktop.

Antes de reutilizar o Notas Flutuantes original, inspecionar seu código e formato de dados numa tarefa específica. Preservar o projeto separado e criar importador explícito, se viável. Não presumir compatibilidade nem copiar sua base silenciosamente.

## 12. Busca global

No MVP, pesquisa por palavras em nomes/títulos, descrições, texto de notas e tags. Normalizar caixa, acentos e espaços. Todas as palavras precisam aparecer no conjunto de campos do item; a ordem pode variar. Não prometer busca semântica, fuzzy ou texto interno de PDFs.

SearchEntry é uma projeção persistida e reconstruível, atualizada na mesma transação da entidade. O texto completo normalizado pode aumentar armazenamento; fica limitado pelos contratos de conteúdo e não contém Blobs. Não construir índice de todas as notas em memória durante o startup.

Primeira implementação: percorrer SearchEntry em lotes de até 200 registros quando houver consulta, manter apenas os 50 melhores resultados e ceder tempo à interface entre lotes. Cada lote usa transação curta e cursor de continuação. Busca parcial é explícita até terminar a varredura. Consultas de IDB não fornecem busca textual completa por si só.

Debounce de aproximadamente 150 ms e identificador de consulta impedem resultados antigos de substituir uma busca mais recente. Fechar o diálogo cancela o processamento. A varredura inicial é O(n); a aceitação de desempenho define se ela basta. Se não passar, introduzir índice invertido incremental em worker atrás do mesmo SearchService, sem carregar uma biblioteca pesada por antecipação.

Ordenação: título exato, prefixo do título, demais correspondências no título, tags e corpo; desempate por atualização. Agrupar resultados por tipo sem esconder seu contexto. Enter abre o item, setas percorrem resultados, Escape fecha e devolve foco ao acionador. Resultado excluído em outra aba produz aviso e atualização da lista.

Em 0.2 adicionar nomes, tags e metadados de arquivos; em 0.3 quadros e notas do quadro; em 0.4 links. Busca dentro do leitor de PDF é separada. Indexação global do texto de todos os PDFs é uma decisão futura de custo, quota e privacidade.

## 13. Atividades, histórico e regras locais

Activity registra fatos úteis: criar/editar/excluir projeto ou nota, criar/concluir/reabrir/adiar tarefa; depois adicionar/abrir arquivo e editar quadro. Não registrar cada tecla, clique, filtro ou movimento intermediário.

Na 0.1 o registro é interno e alimenta as últimas 10 atividades do Dashboard e `lastActivityAt`. A página de histórico completo só entra na 0.4. A mesma transação persiste entidade e evento; notificações de UI vêm após commit, sem um listener gravando história separadamente.

Eventos têm tipo estável, instante, IDs e rótulo curto; não guardam cópias integrais de notas. Edição explícita gera no máximo um evento por salvamento. Mais tarde, abrir PDF gera evento por sessão de leitura, não por página. Activity é append-only, sem remoção automática silenciosa; paginação evita carregar tudo.

Regras do Dashboard 0.1: tarefa pendente vencida; prazo hoje/amanhã; projeto ativo sem atividade por pelo menos 7 dias; tarefa adiada 3 ou mais vezes. Os números reais entram na mensagem, como “Sem atividade há 12 dias”. Limitar a três alertas inicialmente e permitir abrir o filtro relevante. Não chamar esses cálculos de IA.

Semana usa segunda a domingo no fuso local configurado; intervalos de consulta são início inclusivo e fim exclusivo. Revisão 0.5 conta IDs distintos de tarefas com evento de conclusão na semana (reconclusões não duplicam), projetos com atividade, adiamentos e arquivos adicionados. “Dias ativos” é a quantidade de datas com eventos relevantes, não tempo de uso. Tarefas reabertas podem ser identificadas à parte, sem alterar o histórico de conclusões.

Calendário futuro consulta Task.dueDate e Project.dueDate diretamente, junto com Event. Não copiar prazos para eventos paralelos. Lembretes iniciais são exibidos ao abrir a aplicação; alertas garantidos com o aplicativo fechado exigem outra arquitetura e não são prometidos.

## 14. Sistema de backup

### Exportação 0.1

Arquivo `meu-painel-backup-AAAA-MM-DD.json`, com identificador de formato, `formatVersion`, `appVersion`, `exportedAt`, `sourceDatasetId` e coleções de projetos, tarefas, notas e atividades. Preferências portáveis como tema podem ir em seção separada. Nunca exportar caches, SearchEntry, revisão global, handles de browser ou preferências transitórias.

Ler as coleções numa única transação readonly, obtendo um retrato consistente. Depois do término, serializar e gerar o download. Não manter uma transação aberta enquanto executa conversões assíncronas externas. A versão 0.1 só contém texto e metadados, sem binários.

Exportador e importador compartilham o mesmo limite de tamanho suportado, medido em bytes UTF-8. Não gerar silenciosamente um backup que a mesma versão recusará restaurar. Se a base superar esse limite, comunicar a limitação antes da exportação; ampliar a capacidade ou implementar processamento incremental será necessário para suportar esse volume. Validar o round-trip próximo ao limite faz parte do gate do MVP.

Informar que o JSON contém dados pessoais legíveis. Não afirmar que está criptografado. Indicar quando ocorreu a última exportação; isso não comprova que o usuário manteve o arquivo em local seguro.

### Importação e conflitos

1. Escolher arquivo; aplicar limite inicial de 50 MiB antes de ler, com mensagem clara se excedido.
2. Fazer parse e validar identificador, versão, tipos, campos permitidos, tamanhos, datas, enums, IDs únicos por coleção e relações. Versão futura incompatível é recusada sem alterar nada.
3. Migrar formatos antigos suportados em memória; reconstruir objetos a partir de campos permitidos, sem mesclar propriedades arbitrárias no estado da aplicação.
4. Mostrar contagens de itens novos, iguais, conflitantes e referências inválidas, junto com **Mesclar / Substituir / Cancelar**. Erros de integridade bloqueiam a confirmação.
5. Em Mesclar, manter registros locais nos conflitos por padrão; IDs idênticos e conteúdo idêntico são ignorados. Oferecer escolha explícita para usar a versão do backup nos conflitos, com prévia. Não decidir silenciosamente pelo maior `updatedAt` ou `revision`, pois bases podem divergir e relógios podem estar errados.
6. Em Substituir, explicar a remoção dos dados atuais e exigir confirmação específica. Oferecer download do backup atual antes de prosseguir. Não limpar o banco antes de validar tudo.
7. Revalidar a revisão da base dentro da transação de importação; se outra aba modificou a base após a prévia, cancelar e recalcular os conflitos.
8. Aplicar a escolha numa única transação readwrite sobre as coleções afetadas, reconstruir projeções de busca e integridade, e confirmar sucesso apenas no commit. Aborto preserva a base anterior.

Preferências ficam fora da transação de IndexedDB e não são substituídas automaticamente. O usuário pode aplicar o tema importado separadamente. A mesclagem é no nível do registro: não funde parágrafos de notas nem combina subtarefas arbitrariamente. Atividades idênticas não se duplicam; colisão de ID com conteúdo diferente é tratada como conflito.

### Arquivos na 0.2

A biblioteca só estará pronta para uso real quando o backup completo também incluir os bytes. Evoluir para pacote ZIP com manifesto JSON e arquivos por ID; avaliar biblioteca pequena com leitura/escrita incremental nessa etapa. Manter JSON como exportação apenas de metadados com rótulo explícito de que não inclui arquivos, nunca chamá-la de backup completo.

Validar tamanho descompactado, nomes, IDs e integridade antes de substituir. Para pacotes maiores que a memória disponível, planejar importação em área temporária e troca de geração somente após validação; até existir isso, impor limite documentado e rejeitar com segurança. Limpar staging interrompido apenas quando comprovadamente não é a geração ativa.

## 15. Estratégia PWA e funcionamento offline

Na 0.1, todas as operações essenciais são locais depois que o código necessário está disponível. Distribuição por servidor local funciona sem internet enquanto ele estiver ligado. Uma versão hospedada ainda **não terá garantia de reabertura offline**, especialmente para módulos ainda não carregados, até a entrega do cache na 0.5.

Desde a fundação, servir por HTTP em localhost ou por HTTPS; não orientar a abrir `index.html` por `file://`. Manter assets locais e caminhos compatíveis com um subdiretório de hospedagem.

Na 0.5, adicionar manifest, nome, ícones apropriados, start URL, escopo e display. A elegibilidade de instalação varia conforme navegador e plataforma, conforme a [documentação de instalação de PWA](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable).

Service Worker terá precache versionado gerado a partir do build, incluindo shell, módulos das funcionalidades disponíveis e assets do PDF. Isso permite lazy loading na execução sem deixar módulos ausentes no uso offline. Cache Storage guarda recursos da aplicação; arquivos pessoais permanecem apenas no repositório de dados. A API exige contexto seguro, com exceção de desenvolvimento local: [Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API).

Na instalação, só tornar a versão utilizável offline após concluir o cache necessário. Na atualização, manter a versão antiga funcional; avisar que há atualização e ativar após o usuário salvar edições. Não forçar `skipWaiting` com formulários sujos ou abas de versões incompatíveis. Limpar caches antigos depois da ativação bem-sucedida, sem tocar no banco pessoal.

Critério: após uma carga online concluída, reiniciar o navegador offline e abrir todas as rotas entregues, inclusive PDF de arquivo local. Instalação não significa sincronização entre dispositivos nem proteção contra limpeza de dados.

## 16. Performance, acessibilidade e comportamento visual

Listas paginadas em 50 itens, Dashboard limitado a 10 tarefas, 6 projetos e 10 atividades. Mostrar contagem e acesso à lista completa. Ordenação/filtragem não deve exigir montar milhares de nós DOM. Consultas de projetos relacionados são agrupadas para evitar uma leitura por linha.

Carregar módulos sob demanda, atualizar apenas a região afetada, cancelar consultas obsoletas e evitar recomputar toda a aplicação por tecla. Campos de texto não persistem todo o banco. Pesquisa é acionada por interação; PDF e Blobs não entram no carregamento inicial.

Metas de engenharia, ainda não medições: shell inicial até 100 KiB comprimidos de JS/CSS, excluindo módulos lazy; resposta visual a interação comum até 100 ms; conteúdo principal utilizável até 2 s em teste desktop com CPU desacelerada; primeiros resultados de busca até 200 ms após debounce e busca completa até 1 s para 5 mil registros representativos. O benchmark documenta máquina, browser, distribuição de texto e condições. Não promover esses números a garantia sem medir.

Criar fixture sintética de 5 mil registros mistos, com notas de tamanhos variados, e ensaio de 20 mil para observar degradação. Se necessário, otimizar consultas/índices ou busca antes de virtualizar tudo. Memória não deve crescer continuamente ao abrir/fechar telas ou documentos repetidamente.

Interface: fundo neutro, um acento, bordas discretas, raio moderado de 6–10 px, hierarquia por tipografia/espaço e fontes do sistema. Sem fontes CDN, glassmorphism, animações ornamentais ou excesso de cards. Tokens controlam cores, espaçamento, foco, tipografia e dimensões.

Desktop: menu lateral recolhível, cabeçalho com busca/ação contextual e conteúdo com uma ou duas colunas conforme largura. Mobile: menu em gaveta, conteúdo em coluna única, ações essenciais alcançáveis, sem depender de hover. Desktop continua prioridade.

Tema claro/escuro/sistema aplicado antes da primeira pintura para reduzir flashes; tema sistema reage a mudanças do SO enquanto selecionado. Contraste, foco visível e estado não dependem só de cor. Usar labels, botões nativos, diálogos com foco controlado e alvos de toque adequados. Respeitar `prefers-reduced-motion`.

Todo estado de tela tem carregando, vazio, erro e recuperação. Erros de salvamento preservam o texto. Sucesso só é mostrado quando os dados foram persistidos. Testes devem verificar regras e fluxos de risco, não detalhes internos triviais.

## 17. Wireframes textuais das páginas principais

### Estrutura e Dashboard 0.1

```text
┌───────────────────┬────────────────────────────────────────────────────┐
│ Painel pessoal  « │ Buscar em tudo…                         Ctrl + K   │
│                   ├────────────────────────────────────────────────────┤
│ Início            │ Hoje · sábado, 19 de setembro          + Tarefa    │
│ Tarefas           │                                                    │
│ Projetos          │ Hoje e atrasadas              Projetos ativos      │
│ Notas             │ □ Revisar portfólio · hoje    Portfólio · 4/5      │
│                   │ □ Enviar trabalho · atrasada  Próxima: publicar    │
│ Buscar            │ Ver todas                     Prazo: 23 set        │
│                   │                                                    │
│                   │ Atenção                       Atividade recente    │
│                   │ Projeto sem atividade: 8 dias Nota criada…         │
│ Configurações     │ Tarefa adiada 3 vezes         Tarefa concluída…    │
│ Dados neste       │                                                    │
│ dispositivo       │ Estado vazio: crie seu primeiro projeto ou tarefa │
└───────────────────┴────────────────────────────────────────────────────┘
```

### Projetos e página individual

```text
Projetos                                   [Status: ativos ▾] [+ Projeto]
Nome                 Progresso       Próxima tarefa       Prazo
Portfólio            4/5 · 80%       Publicar              23 set
Estudos              Sem tarefas    Adicionar tarefa      —
                                                    [Anterior] [Próxima]

Portfólio                         [Ativo ▾] [Editar] [Arquivar] [Mais…]
Descrição breve · Prazo 23 set · Última atividade hoje
[Visão geral] [Tarefas] [Notas]
Progresso: 4/5 · Próxima tarefa: Publicar
Tarefas recentes / Notas recentes               [+ Tarefa] [+ Nota]
```

### Tarefas e notas

```text
Tarefas                                                    [+ Tarefa]
[Hoje] [Próximas] [Atrasadas] [Concluídas] [Todas]
Projeto [Todos ▾]   Prioridade [Todas ▾]   Tag [Todas ▾]
□ Revisar README        Portfólio       Alta       Hoje     [Editar]
□ Preparar apresentação Sem projeto     Normal     24 set   [Editar]

Notas                                     [Projeto ▾] [Tags ▾] [+ Nota]
┌─────────────────────────┬────────────────────────────────────────────┐
│ Pesquisar notas…        │ Título: IndexedDB                          │
│ IndexedDB               │ Projeto: Painel pessoal      Tags: web     │
│ Ideias para portfólio   │                                            │
│                         │ Texto simples / Markdown como texto        │
│ [Anterior] [Próxima]    │                                            │
│                         │ Alterações não salvas   [Cancelar] [Salvar]│
└─────────────────────────┴────────────────────────────────────────────┘
```

### Busca e backup

```text
Buscar em tudo                                          [Esc para fechar]
[xampp mysql                                                   ]
NOTA      Como recuperar banco do XAMPP          Projeto Servidor PHP
PROJETO   Servidor PHP                           Descrição: XAMPP/MySQL
          ↑ ↓ navegar · Enter abrir

Configurações
Tema                 ( ) Claro  ( ) Escuro  (•) Sistema
Dados                Salvos neste navegador e dispositivo
Backup               [Exportar JSON] [Importar backup]
Prévia de importação 12 novos · 3 iguais · 2 conflitos
Conflitos            [Manter locais ▾] [Revisar diferenças]
                     [Mesclar] [Substituir…] [Cancelar]
```

### Páginas futuras, sem implementação no MVP

```text
Biblioteca   [Buscar] [Tipo ▾] [Projeto ▾] [Ordenar ▾] [+ Arquivos]
             Nome | Tipo | Tamanho | Adicionado | Tags | Projeto

PDF          [Voltar] Nome.pdf  [<] [37 / 120] [>] [-] [100%] [+] [Buscar]
             ┌──────────────── página atual ─────────────────┐ [Tela cheia]
             └───────────────────────────────────────────────┘

Quadros      [Ideias ▾] [+ Nota] [Desfazer] [Refazer] [-] [100%] [+]
             Fundo livre: notas coloridas com texto e poucas ações

Calendário   [<] Setembro [>] [Mês] [Semana] [Próximos] [+ Evento]
             Prazos de tarefas + projetos + eventos próprios

Inbox        [+ Nova captura___________________________________]
             Pesquisar IndexedDB amanhã      [Transformar em…]

Revisão      14–20 setembro     [Semana anterior] [Próxima]
             Concluídas | Projetos atualizados | Parados | Adiadas
             Arquivos adicionados | Dias com atividade
```

## 18. Roadmap por versões

| Versão | Resultado utilizável | Dependência e critério de saída |
| --- | --- | --- |
| 0.1 | Organizar desenvolvimento com projetos, tarefas e notas; encontrar e restaurar dados | CRUD persistente, busca e restauração verificados; sem módulos futuros na navegação |
| 0.2 | Biblioteca local, PDFs, retomada e leituras; pastas/categorias simples | Base 0.1 confiável; backup completo com arquivos e leitor sem carga no startup |
| 0.3 | Quadros livres com vínculo a projeto, anexos e desfazer/refazer | Biblioteca reutilizada para arquivos; mover notas sem gravar a cada frame |
| 0.4 | Calendário, Inbox, links, favoritos e histórico navegável | Relações consistentes; conversão de Inbox atômica; favoritos sem duplicações |
| 0.5 | Revisão semanal, estatísticas úteis e PWA completa | Métricas reproduzíveis; atualização segura; reinício offline validado |
| Futuro | Anotações de PDF ampliadas, sync, Supabase, integrações e IA opcional | Necessidade demonstrada, protocolos de conflito e consentimento definidos |

Cada versão deve ser utilizável antes de iniciar a próxima. Não estimar calendário sem medir capacidade e validar o primeiro incremento. A primeira etapa de desenvolvimento é apenas a fundação descrita no plano; ela não equivale ao MVP inteiro.

## 19. Riscos técnicos e mitigação

| Risco | Consequência | Tratamento planejado |
| --- | --- | --- |
| Limpeza/remoção de armazenamento ou perfil errado | Perda aparente ou real de dados | Mensagem clara, backup desde 0.1, persistência quando disponível, origem estável |
| Mudança de porta/domínio | Outra base vazia | Documentar origem e transferência por backup; não usar porta aleatória silenciosamente |
| Duas abas editando/importando | Sobrescrita de trabalho | Revisão por entidade e base, transações e atualização após commit |
| Migração interrompida/bloqueada | Aplicação indisponível | Migração incremental, tratamento de outras abas, rollback e testes reais |
| Importação inválida ou grande | Corrupção, travamento, referências quebradas | Limites antes de parse, schema validado, prévia e transação atômica |
| Texto/links de origem não confiável | Execução de conteúdo indevido | Renderização textual, protocolo http/https para links, sem HTML arbitrário; sanitização se houver preview futuro |
| Armazenamento local confundido com criptografia | Expectativa incorreta de privacidade | Dados locais sem telemetria, mas acessíveis ao perfil/dispositivo; backup JSON legível |
| PDFs/imagens grandes | Consumo de memória e lentidão | Limites, worker, renderização parcial, liberação de recursos e erros recuperáveis |
| Busca linear não atingir a meta | Experiência lenta com muita informação | Projeção leve, lotes, cancelamento, benchmark e evolução para índice invertido se necessária |
| Histórico crescer indefinidamente | Uso de espaço e backup maior | Eventos pequenos, consultas paginadas e política futura de retenção explícita |
| Datas e fusos tratados como UTC indiscriminadamente | Prazos no dia errado | Separar datas civis de instantes; verificar virada de dia e semana |
| Cache e banco em versões incompatíveis | Falha depois de atualização PWA | Ativação coordenada, migrações compatíveis e testes de atualização |
| Divergência com Notas Flutuantes original | Perda da simplicidade ou importação incorreta | Inspecionar projeto antes de reutilizar; manter módulo independente |
| Escopo crescer antes do uso diário | Projeto grande sem entregar utilidade | Gate por versão, sem scaffolding futuro e aceitação baseada em fluxo real |

Sincronização futura também exigirá tombstones e regras de conflito. Esses campos não entram por especulação no MVP; a migração será parte explícita da versão que introduzir sync. Integrações externas deverão ser opt-in e não transmitir conteúdo de modo implícito.

## 20. O que não implementar agora

Não construir biblioteca, PDF, Quadros, calendário, Inbox, links, favoritos, tela de histórico ou revisão semanal durante o MVP 0.1. O registro mínimo de atividades é infraestrutura do Dashboard, não antecipação da interface completa de histórico.

Não implementar backend, autenticação, Supabase, APIs externas, Gmail, Google Calendar, Drive, GitHub, webhooks, colaboração, criptografia própria, sincronização ou assistente de IA. Nenhum modelo local pesado e nenhuma chamada remota para uma função essencial.

Também ficam fora: editor de blocos, Markdown com HTML arbitrário, OCR, edição completa de PDF, grafo de conhecimento, tarefas recorrentes, Kanban/drag-and-drop sem necessidade comprovada, hierarquia infinita de subtarefas, temporizador de produtividade, sistema genérico de plugins e notificações garantidas em segundo plano.

**Estado atual:** a etapa de planejamento foi seguida pela implementação autorizada do MVP e integração antecipada de Quadros. O roadmap continua sendo referência para as funcionalidades ainda não entregues. Consulte README e VERIFICATION antes de considerar os critérios de homologação de todas as versões concluídos.
