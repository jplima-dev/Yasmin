# Arquitetura do ecossistema Ink

## Objetivo

O Workspace OS é a Home e o Core de integração. Cada ferramenta continua em sua própria pasta e pode manter seu próprio repositório Git. O Core publica apenas contratos pequenos e estáveis; nenhum módulo importa arquivos internos de outro módulo.

```text
Home / módulo
      |
      v
JavaScript Core (Mega)
      |
      +-- Settings + Theme + BroadcastChannel
      +-- Events
      +-- Storage com namespace
      +-- Drop Zone + histórico de arquivos
      +-- atividades, notificações e exportações recentes
      +-- backup e restauração das preferências
      +-- catálogo de módulos
      |
      v
API local 127.0.0.1:8790
      |
      +-- configurações persistentes
      +-- inicialização com o Windows
      +-- processos Bridge e Organizador
      +-- arquivos dos módulos estáticos
```

## Pastas do Core

- `config/modules.json`: manifesto central. Define nome exibido, categoria, tipo, entrada, instruções e inicialização.
- `web/core/settings.js`: API única de configuração visual, persistência otimista, sincronização e assinatura de mudanças.
- `web/core/theme.js`: resolve tema e transforma a cor livre em `--accent`, hover, fundo suave, borda e tokens de superfície.
- `web/core/storage.js`: cria storages `workspace.<namespace>.<key>` para novos módulos.
- `web/core/events.js`: barramento de eventos local desacoplado.
- `web/core/modules.js`: valida manifesto e converte nomes técnicos de pasta em títulos naturais.
- `web/core/module-bootstrap.js`: instala `window.Mega` em páginas de módulos e aplica as configurações globais.
- `../workspace-design-system/src/`: fonte visual efetiva de toda a suíte. O bootstrap injeta `workspace-ui.css`; o Core serve esses arquivos em `/design-system/`.
- `web/core/dom.js`: normaliza botões sem tipo e acompanha elementos inseridos dinamicamente.
- `web/core/module-theme.css`: fornece tokens de compatibilidade, aplica a identidade compartilhada aos módulos legados e corrige hovers, menus, campos e estados escuros.
- `web/core/tool-shell.css`: estrutura visual compartilhada pelas ferramentas utilitárias.
- `web/core/components/terminal.js`: terminal reutilizado como painel flutuante e módulo independente.
- `web/core/dropzone.js`: recepção universal, classificação e entrega de arquivos para campos dos módulos.
- `web/core/activity.js`: API persistente de atividades compartilhada entre origens e módulos.
- `web/core/backup.js`: exportação e restauração versionada das configurações do Workspace.
- `web/core/presets.js`: presets compartilhados e filtrados pelos IDs dos módulos compatíveis.
- `web/core/clipboard.js`: histórico textual interno, compartilhado entre módulos e origens.
- `web/core/components/activity-center.js`: central visual de notificações, exportações e erros.
- `web/core/theme-preload.js`: aplica o tema persistido antes da primeira pintura e evita o clarão branco no modo escuro.
- `workspace_os/`: adaptador Python pequeno para HTTP local, processos, Windows e módulos que precisam do sistema.

## Contrato JavaScript público

Depois de carregar `http://127.0.0.1:8790/core/module-bootstrap.js`, um módulo pode usar:

```js
Mega.settings.get("theme");
Mega.settings.set("accent", "#1a73e8");
Mega.settings.subscribe((settings) => console.log(settings));

const storage = Mega.storage.namespace("meu-modulo");
storage.set("draft", { title: "Rascunho" });

Mega.events.emit("document:opened", { id: "123" });

Mega.ui.toast("Documento salvo", { tone: "success" });
const accepted = await Mega.ui.confirm({ title: "Excluir?", destructive: true });

const pending = await Mega.dropzone.getIncoming();
await Mega.dropzone.deliver();
await Mega.dropzone.send(file, { moduleId: "converter", inputId: "file-input" });
await Mega.presets.save({ name: "Card Instagram", moduleIds: ["photos"], data: { width: 1080, height: 1080 } });
await Mega.clipboard.add("texto reutilizável", { source: "meu-modulo" });
```

Somente a API acima é pública. Arquivos internos de InkWrite, InkSheet, Fotos ou qualquer outro módulo não são dependências válidas.

## Configurações globais

`Settings` mantém uma única configuração com schema e revisão, incluindo tema, cor, densidade, movimento, idioma e composição da Home. Ordem dos favoritos, tamanho dos cards e visibilidade dos indicadores acompanham o mesmo fluxo. Uma alteração:

1. é validada no cliente;
2. é aplicada imediatamente com CSS Variables;
3. atualiza o cache local;
4. é enviada às outras abas por `BroadcastChannel("workspace-os-settings")`;
5. usa o evento `storage` como fallback;
6. é persistida pela API local;
7. é reconciliada periodicamente em páginas com origens/portas diferentes.

O servidor aceita CORS apenas para origens loopback (`127.0.0.1` ou `localhost`). Sites externos não recebem acesso.

## Perfis de Bridge e InkDriver

As configurações não ficam mais reduzidas a um endereço. `module_configs.bridge` controla rede, portas, diretórios e tamanho de transferência; o gerenciador de processos converte o perfil em variáveis de ambiente ao iniciar o serviço. O adaptador `IntegrationProfiles` lê e atualiza o perfil real do agente Windows sem apagar identidade ou chaves de pareamento. `module_configs.drive2` guarda opções não secretas, enquanto senha, segredo e credenciais R2 permanecem somente no formulário até o navegador gerar o `.env`.

## Terminal e caixa-preta

O Ink Terminal possui interface independente em `ink-terminal/`, mas reutiliza o componente do Core em todas as páginas conectadas. A rota compatível `POST /api/terminal/command` continua disponível; a interface usa `POST /api/terminal/processes`, consulta a execução por ID e pode cancelar toda a árvore pelo método `DELETE`. Cada aba conserva pasta, saída, histórico, entrada e processo próprios, incluindo PID, duração, código de saída, memória e CPU quando o sistema fornece essas métricas. O adaptador interno do Windows usa `EncodedCommand` Unicode e saída UTF-8. O executor está em modo irrestrito e não classifica, bloqueia diretórios nem pede confirmação por comando. A autenticação temporária da API, os limites técnicos e a auditoria estruturada com redação de possíveis credenciais continuam ativos. As sugestões combinam atalhos do Workspace, comandos reais do sistema e arquivos; `Tab` aceita a primeira sugestão.

O comando `subdivide` navega para o coordenador `split.html`, que carrega duas instâncias isoladas da URL atual em frames da mesma origem. A barra central pode ser redimensionada e cada frame mantém seu próprio DOM, navegação e estado de execução. Frames enviam comandos ao coordenador por `postMessage` validado pela origem do Core. `unsubidivide` abre uma escolha modal; o frame selecionado é mantido vivo em tela cheia, enquanto o outro é descartado. A URL superior é sincronizada sem recarregar a instância escolhida e, após uma atualização manual, volta ao módulo normal.

Ao executar `python` ou `pip`, o Core procura primeiro o ambiente da pasta atual (`.venv`, `venv`, `env` ou `python.exe`) e só então instalações do sistema. O diretório do interpretador também é acrescentado ao `PATH` daquela execução, permitindo ferramentas do ambiente virtual sem ativação manual. IDs técnicos permanecem estáveis nos contratos internos, mas a interface de comandos usa aliases públicos como `ink-driver`.

Comandos que não pertencem ao Workspace são executados no computador usando a pasta atual da sessão. O Git é detectado automaticamente. Quando a pasta atual pertence a um repositório, o Core injeta `safe.directory` somente no processo do comando, sem alterar a configuração global do usuário.

`BlackBoxStore` registra erros pequenos, requisições mutáveis, acessos a arquivos principais, alterações de configuração e falhas de processo em `blackbox.json`. O navegador envia `error` e `unhandledrejection` ao Core. O Terminal consulta novos eventos e mostra avisos discretos; a Central mantém o painel completo. Conteúdo sensível de comandos bem-sucedidos não é armazenado pela caixa-preta.

## Portabilidade, módulos e Git

`PortableArchive` produz ZIP versionado e seletivo com configurações, presets, clipboard, atividades, arquivos recentes e snapshots autorizados. A importação valida caminhos do ZIP, restaura apenas as seções escolhidas e informa relocação ou caminhos externos ausentes. `launcher.py --portable` troca o diretório de dados para `portable-data`.

`ModuleDataStore` é o contrato opt-in usado por `Mega.backup.register`. O módulo decide exatamente como exportar e importar seu estado. `GitProjects` consulta branch, upstream e árvore suja. Atualizações executam `fetch` seguido de `pull --ff-only` e são recusadas quando há mudanças locais. Manifestos descobertos continuam sem permissão para iniciar comandos.

## Atividades e backup

`ActivityStore` persiste até 250 eventos em `%LOCALAPPDATA%\WorkspaceOS\activity.json`. Todas as páginas conectadas usam `/api/activity`, portanto a central funciona mesmo quando um módulo roda em outra porta. Aberturas de módulos, arquivos da Drop Zone, downloads, backups e erros podem ser registrados por `Mega.activity.record(...)`.

O backup geral usa um JSON versionado. Ele contém configurações globais, favoritos, URLs, perfis não secretos e chaves `workspace.*` do navegador. Não inclui documentos de IndexedDB, arquivos da Drop Zone, senhas ou credenciais de integrações.

## Drop Zone universal

O Core guarda arquivos recebidos em `%LOCALAPPDATA%\WorkspaceOS\dropzone`, com limite de histórico e nomes internos aleatórios. A interface classifica extensão e MIME, consulta o catálogo e oferece somente ações compatíveis. A escolha navega na mesma guia com `?workspaceDrop=<id>&target=<campo>`; no destino, o bootstrap recupera o conteúdo, cria um `File`, preenche o campo solicitado e dispara `change`.

Arquivos são transferidos em blocos de 8 MiB e gravados diretamente no disco, sem o antigo teto fixo de 100 MB e sem manter o conteúdo inteiro na memória do Core. O limite prático passa a ser o espaço livre do disco, o sistema de arquivos e a capacidade do módulo de destino. Pastas são coleções próprias: o Core preserva os caminhos relativos, mostra progresso por arquivo e fornece leitura HTTP com suporte a `Range`. O Analisador de Projetos consome essa coleção sob demanda, sem baixar a pasta inteira antes de iniciar a análise.

Rotas públicas apenas em loopback:

- `GET /api/dropzone/history`: itens recentes;
- `POST /api/dropzone/files`: recebe conteúdo binário e metadados nos cabeçalhos `X-File-*`;
- `GET /api/dropzone/files/<id>/content`: recupera conteúdo;
- `DELETE /api/dropzone/files/<id>`: remove o item e seu conteúdo.
- `POST /api/dropzone/uploads` + `/chunk` + `/complete`: upload grande e incremental;
- `POST /api/dropzone/folders`: cria uma coleção de pasta;
- `GET /api/dropzone/folders/<id>`: lê o manifesto preservando caminhos relativos;
- `GET /api/dropzone/folders/<id>/files/<file-id>/content`: lê um arquivo da pasta, inclusive por intervalo de bytes.

Pastas não são copiadas integralmente: o Core registra o nome e abre o Analisador, que pede a seleção da pasta com a permissão explícita do navegador.

## Dados e namespaces

- Configuração global: arquivo de dados do Workspace OS e cache `workspace.settings.cache`.
- Novo módulo: prefira `Mega.storage.namespace("id-do-modulo")`.
- Módulos existentes com IndexedDB permanecem em bancos próprios durante a migração gradual.
- Configurações específicas permanecem dentro do namespace ou banco do próprio módulo.

## Como a Home carrega módulos

Ao iniciar, a API lê `config/modules.json`, valida IDs e garante que pastas locais não escapem da raiz do ecossistema. Depois procura opcionalmente `ink-module.json` nas pastas diretamente abaixo da raiz do ecossistema. O catálogo central tem precedência em IDs repetidos. Manifestos descobertos podem declarar páginas `static-web`, `remote-web` ou planejadas, mas não podem iniciar comandos ou serviços automaticamente. Módulos `static-web` recebem uma URL como `/module/<id>/<entryFile>`. A Home navega para todos os módulos na guia atual. O bootstrap injeta um retorno discreto para a Home quando o módulo não possui um. Serviços mantêm sua porta própria e aplicativos desktop são iniciados pelo adaptador de processos.

## Dependências e limites

- HTML, CSS e JavaScript são o padrão para Home e ferramentas locais.
- Bridge e InkDriver podem manter Python por dependerem de rede, sistema, servidor ou dispositivo.
- Executáveis Python antigos podem permanecer arquivados como fallback durante a validação, mas as entradas principais do Conversor, Analisador e Leitor já usam JavaScript.
- O Core não conhece documentos, células, fotos ou payloads internos; ele conhece apenas módulos, preferências e execução.
