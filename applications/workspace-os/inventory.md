# Inventário do ecossistema Workspace OS

Data do levantamento: 25/09/2026. O inventário ignora `.git`, ambientes virtuais, `node_modules`, builds e caches. Nenhum projeto existente foi movido ou apagado.

## Resumo executivo

O melhor ponto de integração é preservar os programas como projetos irmãos e usar este repositório, `workspace-os`, como orquestrador. O Organizador já oferece a base visual e integra a fonte do Notas Flutuantes por uma junction; Bridge e Drive2 já possuem serviços Python próprios; Conversor de Arquivos, Organizador de Fotos, Analisador e Leitor podem ser iniciados como ferramentas independentes.

| Projeto | Tecnologia | Estado observado | Decisão |
| --- | --- | --- | --- |
| `organizador` | JavaScript nativo, Vite, IndexedDB, agente Python/WebSocket | MVP funcional, build presente, 4 arquivos de testes; sem `.git` local | **Reutilizar** como centro de trabalho |
| `notas-flutuantes` | HTML, CSS, JavaScript, IndexedDB | Funcional, Git próprio e árvore limpa | **Reutilizar** pela integração já existente |
| `organizador-fotos` | HTML, CSS e JavaScript | Seis telas, sem testes automatizados e sem `.git` local | **Adaptar** gradualmente; disponível como módulo estático |
| `conversor-arquivos` | Python, pywebview, Pillow, bibliotecas de documentos/dados | Aplicativo funcional, Git próprio; sem testes detectados | **Reutilizar**, depois expor contrato de conversão |
| `bridge` | FastAPI, SQLite, WebSocket/HTTP, agente Windows e cliente Android | Serviço estruturado, 3 arquivos de testes; `.venv` presente; sem `.git` local | **Reutilizar** como serviço de dispositivos |
| `driver` (Drive2) | FastAPI, SQLite, HTML/CSS/JS, R2/Gmail opcionais | v1.0 documentada, 5 arquivos de testes mais relatório, boot do Termux pronto; sem `.git` local | **Reutilizar**; recomenda-se renomear o repositório remoto para Drive2 no futuro sem mover a pasta agora |
| `analisador-projetos` | Python, pywebview, HTML/CSS/JS | Funcional, Git próprio, 1 arquivo novo não versionado (`assets/screenshots/logo_p.png`) | **Reutilizar** como utilitário |
| `leitor_projetos` | Python, Tkinter, PyInstaller | Funcional, Git próprio, 1 arquivo novo não versionado (`assets/screenshots/logo.png`) | **Reutilizar** como utilitário |
| `planta-baixa-maker` | HTML/CSS/JavaScript | Git próprio e árvore limpa; fora do escopo central atual | **Manter independente**, não carregar no início |
| `portifolio` | HTML/CSS/JavaScript | Git próprio, árvore limpa; fora do produto | **Descartar da integração**, preservar arquivos |
| `analisador-projetos`, `audio`, `freelancer`, `img` | Misto/ativos auxiliares | Não são dependências do núcleo | **Preservar fora do autostart** |

## Dependências e riscos

### Organizador

- Porta fixa: `5173`.
- O armazenamento IndexedDB depende exatamente da origem; trocar `127.0.0.1`, porta ou protocolo cria outra área de dados.
- A integração de Notas Flutuantes compartilha código, não o banco do navegador.
- Requer Node.js 22.12+ no desenvolvimento/servidor Vite. O build já existe.

### Bridge

- Porta fixa: `8876`.
- A `.venv` e o Core estão presentes e podem ser iniciados por `scripts/start.ps1`.
- Antes deste orquestrador, a tarefa automática cobria apenas o agente Windows, não o Core.
- Dados persistentes ficam em `bridge/.data` e arquivos recebidos em `bridge/received`; não devem ser apagados como tentativa genérica de correção.

### Drive2

- Porta padrão: `8000`, normalmente no IP Tailscale do tablet.
- A inicialização automática já é prevista pelo script `scripts/termux-boot-drive2` e pelo Termux:Boot.
- R2 e Gmail são opcionais e não devem ser habilitados antes do núcleo local funcionar.
- O nome da pasta local é `driver`, mas o pacote e a documentação usam `drive2`. O orquestrador mascara essa inconsistência sem fazer uma movimentação destrutiva.

### Conversor

- O ambiente virtual local foi encontrado.
- PDF, DOCX, XLSX e imagens dependem das bibliotecas listadas em `requirements.txt`.
- A ausência de testes automatizados pede uma fase própria antes de expor conversão a outros módulos.

## Reutilização por categoria

### Reutilizar

- Shell e dados do Organizador.
- Notas Flutuantes e sua ligação de código.
- APIs e banco do Bridge.
- API, banco, fila e políticas do Drive2.
- Conversores atuais e os dois utilitários de projetos.

### Adaptar

- Organizador de Fotos: criar manifesto, testes e exportação por um serviço PDF comum.
- Conversor: separar a camada de conversão da janela pywebview para permitir API local.
- Bridge: mover a configuração de autostart para o Workspace OS e manter o agente como componente opcional.
- Drive2: cadastrar URL Tailscale no painel e tratar indisponibilidade sem derrubar o restante.

### Refazer apenas onde necessário

- Não há justificativa para reescrever projetos funcionais.
- Recursos novos — QR Code, Mini Word e Mini Excel — deverão nascer em pastas e repositórios próprios, com manifesto e contrato público desde o início.

### Não integrar

- Portfólio, mídia solta e trabalhos sem relação direta com o fluxo do Workspace OS.
- Artefatos gerados (`dist`, `node_modules`, `.venv`, caches) como fonte de integração.

## Estado Git observado

Repos Git existentes e limpos: `notas-flutuantes`, `planta-baixa-maker`, `portifolio`.

Repos Git com arquivo não rastreado, preservado sem alteração:

- `analisador-projetos/assets/screenshots/logo_p.png`;
- `conversor-arquivos/assets/screenshots/logo.png`;
- `leitor_projetos/assets/screenshots/logo.png`.

`organizador`, `organizador-fotos`, `bridge` e `driver` não tinham pasta `.git` durante o levantamento. Este inventário não inicializa Git neles para não inventar remotos ou históricos.

## Primeira fase escolhida

**Fase 1 — Core de integração.** Entrega neste repositório:

- painel local em `http://127.0.0.1:8790`;
- catálogo e diagnóstico dos projetos irmãos;
- início/parada apenas de processos iniciados pela sessão;
- autostart do Core, Organizador e Bridge no login do Windows;
- tema, cor, densidade e URL do Drive2;
- guia de primeiro uso dentro da própria interface;
- persistência em `%LOCALAPPDATA%/WorkspaceOS`;
- módulos futuros visíveis como planejados, sem telas falsas.

## Atualização da Fase 2

O primeiro projeto novo foi criado fora do Core, em `../gerador-qrcode`, com Git, testes e build próprios. O catálogo o serve por manifesto como módulo estático; o código e as dependências não entram neste repositório.

## Atualização visual

O projeto independente `../workspace-design-system` foi criado para manter tokens e componentes compartilháveis sem acoplar os aplicativos em runtime. Workspace OS, Organizador e Gerador de QR Code receberam a primeira aplicação da linguagem clara e neutra; a migração dos demais módulos será incremental para evitar regressões em ferramentas já funcionais.

## Atualização de utilitários e terminal

Foram acrescentados cinco projetos irmãos independentes: `ink-json`, `ink-palette`, `ink-diff`, `ink-base64` e `ink-terminal`. Eles usam HTML, CSS e JavaScript, compartilham somente contratos públicos do Core e aparecem automaticamente no catálogo e no `Ctrl+K` por meio do manifesto.

O terminal possui duas entradas para o mesmo componente: painel flutuante na Home e módulo em tela cheia. A execução acontece no Core local por PowerShell ou CMD, com histórico no navegador, pasta atual por sessão, limite de tempo e resposta estruturada. Favoritos também passaram a ser configuração global sincronizada, substituindo o antigo acesso rápido fixo.
