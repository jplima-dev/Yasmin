# Catálogo de módulos

| Nome | Pasta | Entrada principal | Dependências | Configurações/dados |
|---|---|---|---|---|
| Organizador | `organizador/` | serviço em `127.0.0.1:5173` | Node.js no desenvolvimento; Core global | IndexedDB `organizador-pessoal`; preferências `organizador:*` |
| Notas Flutuantes | `notas-flutuantes/` | `index.html` servido em `/module/notes/` | navegador; Core global | `localStorage` exclusivo do módulo; backup JSON próprio |
| Organizador de Fotos | `organizador-fotos/` | `index.html` | navegador; Core global | IndexedDB `fotogrid-studio`; chaves `fotogrid-*` |
| Conversor de Arquivos | `conversor-arquivos/` | `web/index.html` | JavaScript, Canvas e APIs de arquivo do navegador | arquivos selecionados na sessão; não envia nem persiste conteúdo |
| Bridge | `bridge/` | serviço configurável, padrão `127.0.0.1:8876` | Python, rede local e dispositivos | `module_configs.bridge`; perfil real do agente em `%LOCALAPPDATA%\Bridge\agent.json` |
| InkDriver | `driver/` | servidor do tablet | Python/Termux, Tailscale e dispositivo | `module_configs.drive2`, URL global e `.env` gerado; dados no tablet |
| Analisador de Projetos | `analisador-projetos/` | `frontend/index.html` | JavaScript, seletor de pasta do navegador e Core global | idioma global; leitura autorizada pelo usuário |
| Leitor de Projetos | `leitor_projetos/` | `web/index.html` | JavaScript e seletor de pasta do navegador | filtros locais e downloads Markdown/TXT; segredos são bloqueados |
| InkWrite | `ink_write/` | `index.html` | navegador; Core global | IndexedDB `inkwrite-studio`; `inkwrite-last-document` |
| InkSheet | `ink_sheet/` | `index.html` | navegador; Core global | IndexedDB `planilha-studio`; `planilha-studio-last-project` |
| Gerador de QR Code | `gerador-qrcode/` | `dist/index.html` | JavaScript, Vite e pacote `qrcode` | não persiste o conteúdo; gera PNG/SVG/PIX localmente |
| Ink JSON | `ink-json/` | `index.html` | JavaScript e Core global | arquivo somente durante a sessão; download explícito |
| Ink Palette | `ink-palette/` | `index.html` | JavaScript e Core global | cor atual somente durante a sessão; exporta CSS |
| Ink Diff | `ink-diff/` | `index.html` | JavaScript e Core global | textos somente durante a sessão; exporta `.diff` |
| Ink Base64 | `ink-base64/` | `index.html` | File APIs do navegador e Core global | arquivos somente durante a sessão; exportação explícita |
| Ink Terminal | `ink-terminal/` | `index.html` | Core local, executor assíncrono e componente compartilhado | histórico limitado `workspace.terminal.history`; estado e saída por aba; auditoria rotativa no Core |

## Regras do catálogo

- Cada pasta possui um `ink-module.json`, que é a fonte de verdade para nome, entrada, versão, recursos, permissões e migrações de dados.
- `config/modules.json` contém somente configuração do Core: origem local, ordem visual e módulos autorizados a iniciar processos. O Core ainda lê contratos legados apenas para compatibilidade.
- `id` é contrato técnico e não deve ser renomeado apenas por mudança visual.
- Cada pasta deve poder ser testada e versionada sem carregar as outras.
- Um módulo pode depender do Core, mas não dos arquivos internos de outro módulo.
- Um manifesto inválido é isolado e aparece no Diagnóstico; ele não impede os outros módulos de carregar.

## Recursos descobertos

O campo `capabilities` declara `export`, `import`, `print`, `offline`, `shortcuts` e `permissions`. A API `GET /api/modules/capabilities` permite que o Core e integrações consultem esses recursos sem conhecer a implementação de cada ferramenta.

`dataSchemaVersion` e `migrations` formam o contrato de dados. Migrações são declarativas (`rename`, `default` e `remove`), rodam em sequência e geram backup antes da gravação atômica.

## Segurança e ciclo de vida

- Toda API mutável exige o token temporário obtido em `GET /api/session`.
- O cliente envia `Idempotency-Key`; mutações concorrentes equivalentes e replays são rejeitados.
- O Ink Terminal executa comandos PowerShell sem restrição de diretório, classificação de risco ou confirmação por comando; a sessão local da API e os limites técnicos do executor continuam obrigatórios.
- Logs JSONL ficam separados por módulo em `logs/modules`, com rotação por tamanho e limpeza por retenção.
- Atualizações Git guardam a revisão anterior, validam manifesto/entrada/saúde e executam rollback automático em caso de falha.
