# Arquitetura do Workspace OS

## Decisão central

O Workspace OS é uma federação de projetos, não um repositório monolítico. Este projeto conhece apenas manifestos, comandos públicos, endereços e estado de saúde. Ele não importa detalhes internos de outro aplicativo.

```text
codigos/
├── workspace-os/          # orquestrador e painel; Git próprio
├── organizador/           # aplicação independente
├── notas-flutuantes/      # aplicação independente; Git próprio
├── organizador-fotos/     # aplicação independente
├── conversor-arquivos/    # aplicação independente; Git próprio
├── bridge/                # serviço independente
├── driver/                # Drive2 independente
├── gerador-qrcode/        # ferramenta offline independente; Git próprio
└── workspace-design-system/ # tokens/componentes visuais; Git próprio
```

Projetos novos serão criados no mesmo nível, por exemplo:

```text
codigos/
├── gerador-qrcode/
├── editor-texto/
└── planilha-simples/
```

Cada pasta nova deverá conter seu próprio `README.md`, `.gitignore`, testes, manifesto e repositório Git. O `workspace-os/config/modules.json` apontará para a pasta irmã; nenhum código-fonte será copiado para dentro do orquestrador.

## Sistema visual

O projeto irmão `workspace-design-system` concentra tokens e componentes CSS reutilizáveis. A direção usa superfícies neutras, tipografia simples, azul apenas para ação/seleção, bordas e sombras discretas — sem neon, glow ou gradientes decorativos.

Cada aplicativo continua independente: durante o desenvolvimento pode importar o pacote, mas o build incorpora o CSS necessário. Assim, nenhum módulo depende do Design System estar executando para abrir.

O Workspace OS, o Organizador e o Gerador de QR Code são as primeiras interfaces alinhadas a essa linguagem. Novos módulos devem começar pelos tokens `--ws-*` e respeitar foco visível, contraste e preferência de redução de movimento.

O Core mantém preferências de densidade, tamanho de texto, movimento e estado da barra lateral no mesmo armazenamento local versionado. A paleta `Ctrl + K` pesquisa apenas o catálogo já carregado no navegador; ela não indexa nem envia conteúdo pessoal.

## Fluxo de inicialização

```text
Login no Windows
      ↓
WorkspaceOS.vbs na pasta Inicializar
      ↓
launcher.py em pythonw (sem terminal)
      ↓
Core HTTP 127.0.0.1:8790
      ├── Organizador 127.0.0.1:5173
      └── Bridge Core 127.0.0.1:8876
```

O Drive2 permanece no boot do tablet. Aplicativos desktop e ferramentas estáticas iniciam sob demanda.

## Dados

| Dado | Local | Motivo |
| --- | --- | --- |
| Preferências e URLs do orquestrador | `%LOCALAPPDATA%/WorkspaceOS/settings.json` | Fora do código e do OneDrive |
| Logs de processos iniciados | `%LOCALAPPDATA%/WorkspaceOS/logs/` | Diagnóstico sem poluir projetos |
| Dados do Organizador | IndexedDB da origem `127.0.0.1:5173` | Preserva comportamento existente |
| Dados do Bridge | `bridge/.data` e `bridge/received` | Propriedade do módulo |
| Dados do Drive2 | SQLite e arquivos no tablet | Propriedade do módulo |

As configurações usam `schema_version: 1`. Mudanças futuras exigem migrações explícitas.

## Comunicação JavaScript ↔ Python

O painel usa HTTP JSON apenas no loopback:

```text
web/app.js
   ↓ fetch /api/*
workspace_os/server.py
   ├── SettingsStore
   ├── ModuleRegistry
   ├── ProcessManager
   └── WindowsStartup
```

O servidor rejeita mutações quando `Host` ou `Origin` não é local. Comandos não chegam do navegador: são declarados no manifesto versionado, o que impede execução arbitrária de shell pela API.

Quando módulos precisarem trocar dados, a próxima camada será formada por contratos versionados e eventos. O Core não acessará tabelas internas de Bridge ou Drive2.

## Limites de processo

- O botão **Parar** encerra somente processos que a sessão atual iniciou.
- Um serviço já ativo externamente é detectado pela porta e preservado.
- A falha de um módulo vira estado/erro do card, sem encerrar o Core.
- Aplicativos desktop não entram no autostart por padrão.
- O orquestrador não instala dependências automaticamente durante o login.

## API atual

| Método | Rota | Uso |
| --- | --- | --- |
| `GET` | `/api/health` | Saúde do Core |
| `GET` | `/api/modules` | Catálogo e estados |
| `POST` | `/api/modules/{id}/start` | Inicia comando declarado |
| `POST` | `/api/modules/{id}/stop` | Para processo pertencente à sessão |
| `GET/POST` | `/api/settings` | Preferências locais |
| `GET` | `/api/diagnostics` | Diagnóstico sem conteúdo privado |
| `GET` | `/api/startup` | Estado do autostart |
| `POST` | `/api/startup/enable` | Cria inicialização do usuário |
| `POST` | `/api/startup/disable` | Remove inicialização do usuário |

## Estado atual e próximas fases

O catálogo modular, InkWrite, InkSheet, QR Code, Drop Zone, Terminal, tema global, Bridge, InkDriver, backup e central de atividades já fazem parte do Core atual.

As próximas fases do orquestrador são contratos de **Abrir com/Enviar para**, presets compartilhados, personalização avançada do dashboard, descoberta opcional de manifestos e empacotamento portátil. Melhorias internas de cada módulo permanecem no repositório correspondente.
