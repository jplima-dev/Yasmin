# Funcionalidades do Agent Core da Yasmin

Este documento descreve o **código implementado atualmente** em `Agent/agente/`,
suas ligações com a Yasmin e seus limites. O Agent Core é a camada que decide
como tratar uma entrada, mantém o estado do objetivo e coordena percepção,
memória, plano, ferramentas e verificação. Ele não é um modelo de IA nem a
interface gráfica.


## Onde o Agent Core entra

```text
Voz (Google Speech) ou texto do Workspace
    → Agent/yas.py: processar_comando()
    → Agent/yas.py: _processar_comando()
    → NucleoAgente.atender()
       ├─ objetivo reconhecido → executar plano e verificar
       ├─ conversa → ServicoConversacao
       ├─ comando legado → devolver ao despachante existente
       └─ pedido ambíguo → pedir esclarecimento
```

`Agent/yas.py:inicializar_agente()` cria uma instância compartilhada do
`NucleoAgente` com seus perceptores, mecanismo de raciocínio, planejador,
registro de ferramentas, verificador e repositório de memória. A entrada por
voz e a janela do Workspace usam `processar_comando()`; uma trava serializa
os comandos para que compartilhem o mesmo estado. O launcher expõe essa
entrada à janela por `Agent/launcher.py:iniciar_interface_workspace()` e
`Agent/servicos/comandos_workspace.py`.

## O que o núcleo faz

| Capacidade | Funcionamento atual | Código |
| --- | --- | --- |
| Decidir a via da interação | Escolhe objetivo, conversa, comando legado ou esclarecimento. Regras locais tratam casos claros; um classificador local treinado cobre duas famílias de objetivo e o classificador remoto continua opcional. Ambos só podem propor operações permitidas. | `Agent/agente/decisao.py`, `Agent/agente/modelo_treinavel.py`, `Agent/agente/nucleo.py:atender()` |
| Diferenciar comando de objetivo | Um pedido de abrir aplicativo vira uma etapa; preparar o ambiente de programação gera localização e abertura com dependência. | `Agent/agente/modelos.py`, `Agent/agente/planejamento.py` |
| Perceber | Estrutura a entrada do usuário e o resultado de cada ferramenta como observações com tipo, fonte, dados, confiança e horário. Perceptores de aplicações podem ser registrados. | `Agent/agente/percepcao.py`, `Agent/agente/integracao_aplicacoes/estado.py` |
| Manter estado | Registra objetivo, plano, etapa, ferramenta, ação, último resultado, última observação, erro, aplicativo ativo e status. | `Agent/agente/modelos.py:EstadoAgente`, `Agent/agente/nucleo.py` |
| Recuperar memória | Consulta registros relacionados ao objetivo, em quantidade limitada, antes do planejamento. | `Agent/infraestrutura/mysql_memoria.py:recuperar()` |
| Planejar e executar | Cria etapas com parâmetros, dependências, status, tentativas e verificação; executa até concluir, bloquear, falhar, cancelar ou atingir o limite de ações. | `Agent/agente/planejamento.py`, `Agent/agente/nucleo.py:executar()` |
| Verificar | Classifica evidências como sucesso, falha ou incerto. Uma função ter retornado não basta para concluir a etapa. | `Agent/agente/verificacao.py`, adaptadores |
| Replanejar | Na preparação do ambiente tenta o editor alternativo; se o resumo padrão já existir, escolhe um novo nome sem sobrescrevê-lo. | `Agent/agente/planejamento.py:replanejar()` |
| Proteger ações de risco | Ferramentas declaram risco baixo, médio ou alto. Risco alto exige confirmação explícita no núcleo e no executor. | `Agent/agente/modelos.py:Risco`, `Agent/agente/ferramentas.py` |
| Conversar | Mantém contexto curto, aplica preferências, responde casos locais e pode consultar memória ou um motor de diálogo opcional. | `Agent/agente/conversacao.py`, `Agent/agente/nucleo.py:conversar()` |
| Cancelar e observar status | Cancela etapas pendentes e impede a próxima ação; divulga o status operacional à interface. | `Agent/agente/nucleo.py:cancelar()`, `Agent/yas.py:estado_atual()` |

Os status do agente incluem `interpretando`, `respondendo`, `planejando`,
`executando`, `concluido`, `falhou`, `bloqueado`, `confirmacao` e
`cancelado`. Etapas podem estar pendentes, executando, concluídas, falhas,
incertas, canceladas ou ignoradas.

## Objetivos e comandos planejados hoje

Estes pedidos possuem caminhos concretos no `Planejador`; exemplos de frase
podem variar dentro das regras reconhecidas:

| Pedido | Plano e verificação |
| --- | --- |
| “Prepare meu ambiente de programação.” | Localiza VS Code e abre o aplicativo; confirma executável e processo. Se falhar, tenta IntelliJ. |
| “Prepare meu ambiente para programar Java.” | Prefere IntelliJ e usa VS Code como alternativa. |
| “Abra o VS Code.” | Comando de uma etapa, quando o identificador do aplicativo é reconhecido pela entrada legada; confirma processo ativo. |
| “Feche o VS Code.” | Pede confirmação antes de encerrar à força; verifica que o processo terminou. |
| “Yasmin, abra a Workspace.” | Descobre o `workspace-os`, abre sua interface e verifica a resposta local. Também pode abrir aplicações encontradas pelo nome no catálogo. |
| “Liste as aplicações disponíveis.” | Descobre e devolve o catálogo de aplicações Ink-guginha. |
| `Analise o projeto em "C:\meu-projeto".` | Usa o Analisador de Projetos e confere caminho e estatísticas retornadas. |
| `Liste os arquivos do projeto C:\meu-projeto.` | Usa os filtros do Leitor de Projetos, sem ler o conteúdo; confirma a listagem por nova consulta. |
| `Leia o projeto "C:\meu-projeto" e me diga o que ele faz.` | Analisa o projeto e consulta a descrição do README ou manifesto; se ausente, informa que não pode afirmar o propósito. |
| `Gere um README chamado GUIA.md na pasta "C:\meu-projeto".` | Analisa, cria Markdown factual sem sobrescrever e confirma o conteúdo gravado. |
| `Abra o Leitor de Projetos, gere o resumo de "C:\meu-projeto" e coloque na pasta "C:\saida".` | Abre o Leitor, exporta o contexto Markdown pelos filtros da aplicação e grava um resumo factual no destino; verifica cada etapa. |
| `Inspecione o repositório "C:\meu-projeto", liste os arquivos e grave GUIA.md na pasta "C:\saida".` | Compõe três ferramentas registradas em sequência: análise, listagem e escrita, com verificação de cada etapa. |
| `Monte um relatório resumido do projeto "C:\meu-projeto" e salve na pasta "C:\saida".` | Analisa, grava `resumo_projeto.md` e, se esse nome já existir, tenta um nome novo sem sobrescrever. |
| “Liste meus cadernos do Ink Notebook.” | Abre o Ink Notebook, consulta sua API local e confere a lista novamente. |

O reconhecimento local compõe ações de projeto como inspecionar, descrever,
listar arquivos e escrever documentação quando o pedido contém os caminhos
necessários. Um motor semântico opcional pode propor outras sequências, mas
cada ferramenta, parâmetro e caminho é validado contra o registro antes do
planejamento. Frases desconhecidas não autorizam operações inventadas. Os
caminhos precisam ser explícitos; use aspas quando contêm espaços. Quando
faltam, a Yasmin pede esclarecimento. O resumo é factual, baseado em
metadados e documentação existente, e não substitui uma análise semântica
profunda de código não documentado.
Os métodos `pular()`, `voltar()` e `adicionar()` existem no planejador para
uso programático; ainda não são comandos de voz expostos ao usuário.

## Ferramentas disponíveis

Todas usam o mesmo `RegistroFerramentas`, `Executor` e `Verificador`.
Executores recebem parâmetros nomeados e devolvem
`ResultadoFerramenta(sucesso, resultado, erro)`.

| Ferramenta | Risco | O que verifica ou observa |
| --- | --- | --- |
| `localizar_aplicativo` | baixo | Caminho de um executável catalogado. |
| `abrir_aplicativo` | médio | Processo esperado em execução no Windows. |
| `fechar_aplicativo` | alto | Ausência do processo após encerramento confirmado. |
| `pesquisar_web` | baixo | Presença de resultados na busca online. |
| `listar_aplicacoes_ink` | baixo | Catálogo atual e ausência de erros nos manifestos. |
| `consultar_estado_aplicacao_ink` | baixo | Identificação e disponibilidade de uma aplicação. |
| `abrir_aplicacao_ink` | médio | Interface HTTP local acessível e, quando aplicável, saúde do serviço. |
| `analisar_projeto_ink` | baixo | Pasta e estatísticas coerentes com a análise. |
| `listar_arquivos_projeto_ink` | baixo | Classificação confirmada por consulta ao Leitor de Projetos. |
| `exportar_contexto_projeto_ink` | médio | Diretório exclusivo e arquivos Markdown realmente criados pelo Leitor. |
| `descrever_projeto` | baixo | Caminho, descrição de manifesto/README e estatísticas observadas. |
| `escrever_resumo_projeto` | médio | Arquivo novo e hash do conteúdo gravado. |
| `listar_cadernos_ink` | baixo | Lista confirmada pela API do Ink Notebook. |

`pesquisar_web` está registrado no núcleo, mas o planejador atual não cria
uma etapa de pesquisa a partir de uma frase genérica. Pedidos comuns de
pesquisa na internet continuam atendidos pelo despachante legado em
`Agent/yas.py` e `Agent/comandos_yasm.py`. A Yasmin permanece híbrida:
capacidades locais não dependem de um provedor de IA, enquanto busca e
serviços online podem usar a internet.

## Aplicações conectadas ao ecossistema

`Agent/agente/integracao_aplicacoes/descoberta.py` lê os manifestos de
`applications/` e inclui o Workspace OS. Os contratos declaram identidade,
versão, fornecedor, autor, interface e eventuais operações do agente. O
fornecedor e autor das aplicações é **Ink-guginha**.

O catálogo atual contém 16 aplicações: Workspace OS (`workspace-os`),
Analisador de Projetos (`project-analyzer`), Leitor de Projetos
(`project-reader`), Ink Notebook (`notebook`), Bridge (`bridge`),
InkDriver (`drive2`), Gerador de QR Code (`qrcode`), Ink Base64
(`base64`), Ink Diff (`diff`), Ink JSON (`json`), Ink Palette
(`palette`), Ink Terminal (`terminal`), InkSheet (`sheets`), InkWrite
(`writer`), Notas Flutuantes (`notes`) e Organizador (`organizer`).

O agente consegue descobrir, consultar disponibilidade e solicitar a abertura
de suas interfaces gráficas, sujeita à instalação e à resposta do Workspace
OS. Operações internas implementadas e expostas como ferramentas existem
especificamente no Analisador de Projetos, no Leitor de Projetos e no Ink
Notebook. As demais aplicações **não** ganharam comandos internos
arbitrários. Suas interfaces continuam sendo aplicações independentes.

O perceptor de aplicação informa `disponivel`, `servico_ativo`, versão e
fornecedor. O campo `aberta` é `null` nessa observação: a mera presença do
manifesto não confirma que uma janela esteja aberta. A abertura é verificada
separadamente por acesso à página e, para serviços, por health check. Isso
confirma a interface HTTP, mas não prova foco da janela nem carregamento de
um projeto específico.

## Memória e aprendizado por experiência

O repositório do agente usa o database MySQL `yasm`; sua preparação cria as
tabelas e índices quando o banco existe. `MemoriaMySQLDisponivel` prepara e
migra os JSONs antigos em segundo plano, preservando os originais. As
credenciais ficam nas variáveis `YASM_MYSQL_HOST`, `YASM_MYSQL_PORT`,
`YASM_MYSQL_USER` e `YASM_MYSQL_PASSWORD`.

Há registros de perfil, preferências, fatos, objetivos, experiências e dados
migrados. O armazenamento inclui importância, confiança, origem, datas de
criação/atualização/último uso e possível expiração. A busca usa termos do
objetivo, ordena por correspondência e importância e limita o retorno; o
núcleo não carrega toda a base a cada interação.

Depois de **preparar o ambiente de programação com sucesso verificado**, o
agente registra qual editor funcionou. Uma solicitação futura semelhante pode
usar essa experiência para escolher o editor inicial, mas verifica novamente
o estado real. A conversa permite ensinar, corrigir ou esquecer fatos
explícitos quando o MySQL está disponível. Os JSONs legados continuam em uso
para compatibilidade.

## Configuração inicial e conversa

`Agent/agente/configuracao.py` contém as perguntas-base, variações, escolhas
permitidas e interpretação das respostas da primeira configuração. A sessão
acompanha o tópico atual, aceita frases completas, responde perguntas feitas
durante a configuração e produz confirmações relacionadas à escolha. As
perguntas priorizam necessidades de quem desenvolve software. A interface em
`Agent/interface/config_inicial.py` apresenta e escuta; o núcleo decide a
próxima pergunta. O resultado é salvo no formato legado e as preferências
úteis são sincronizadas com MySQL quando a memória está ativa.

`ServicoConversacao` usa contexto curto, preferências de tom e tamanho de
resposta, regras para casos simples, recuperação de memória relevante e um
motor de diálogo opcional. A implementação configurada para o motor externo
fica em `Agent/infraestrutura/dialogo_groq.py`; o núcleo não importa o
fornecedor. Sem o serviço externo, permanecem as respostas locais e
capacidades determinísticas, com conversa livre mais limitada.

## Modelo local treinável

`Agent/agente/modelo_treinavel.py` implementa um classificador de intenções
local, treinável e independente de fornecedor. O arquivo
`Agent/modelos/intencoes_local.json` guarda seus parâmetros em JSON. Na
inicialização, `Agent/yas.py` o carrega uma vez; se o arquivo estiver
indisponível ou inválido, as regras anteriores e o motor externo opcional
continuam funcionando.

O primeiro treinamento executado processou **1.000 frases distintas e
rotuladas**: 400 de preparação do ambiente, 300 de listagem das aplicações e
300 exemplos fora dessas operações. A avaliação separada acertou **30/30**
frases, inclusive recusas de pedidos destrutivos e de tarefas ainda não
suportadas. Esse conjunto é pequeno e gerado por variações de frases; o
resultado não mede compreensão geral de linguagem.

O classificador só propõe `preparar_programacao` ou
`listar_aplicacoes_ink`, com limiares de confiança e evidência textual. Ele
se abstém diante de negações, exclusões, instalações, pedidos compostos e
perguntas explicativas. O `DecisorInteracao` valida a proposta; plano,
executor, confirmação de risco e verificação seguem os mesmos componentes do
Agent Core. Treinar o classificador **não cria** ferramentas ou planos novos.
Ele também não treina a voz neural nem um LLM de conversa.
Os pedidos de projeto usam extração local em `Agent/agente/pedidos_dev.py`,
composição de ações em `Agent/agente/composicao_local.py` e validação de planos
propostos em `Agent/agente/planos_ferramentas.py`. O planejador existente
transforma cada ação aceita em etapa verificável. Essa composição não foi
treinada pelo classificador de 1.000 frases; novas capacidades continuam
exigindo ferramenta real e verificação implementada.

Para acrescentar exemplos seus, crie um arquivo JSONL com uma linha por
frase e rótulo:

```json
{"texto":"Estou precisando de uma IDE para trabalhar com Kotlin","rotulo":"preparar_programacao"}
{"texto":"Mostre os módulos que posso abrir","rotulo":"listar_aplicacoes_ink"}
{"texto":"Quero conversar sobre Kotlin","rotulo":"nenhuma"}
```

Os únicos rótulos aceitos são `preparar_programacao`,
`listar_aplicacoes_ink` e `nenhuma`. Na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe Agent/treinar_agente.py --dados meus_exemplos.jsonl
```

O script recompõe os 1.000 exemplos-base, acrescenta os seus, avalia frases
separadas do treino e só substitui o modelo se a avaliação superar o limite
e não houver falsos positivos nos casos de segurança. Reinicie a Yasmin
depois do treino para carregar o novo arquivo. O aprendizado por experiência
no MySQL continua separado desse treinamento de interpretação.

## Outros pontos de uso

- `Agent/yas.py` inicializa o núcleo, entrega cada entrada a `atender()`,
  encaminha comandos legados quando necessário e expõe `estado_atual()`.
- `Agent/launcher.py` recebe comandos da janela, chama
  `yas.processar_comando()` e informa o estado operacional à interface.
- `applications/workspace-os/web/yasmin-ui.js` apresenta as barras no topo,
  consulta fala e etapa atual e oferece a conversa ao clicar nelas; a aba
  lateral antiga da Yasmin foi removida.
- `Agent/interface/config_inicial.py` usa `SessaoConfiguracao` com a
  instância do agente e o serviço de conversa.
- `Agent/agente/integracao_aplicacoes/` conecta manifestos, perceptores,
  ferramentas, abertura e verificadores ao núcleo existente.
- `Agent/infraestrutura/` concentra MySQL e o provedor opcional de diálogo.
- `Agent/apps_yas.py` e `Agent/comandos_yasm.py` fornecem recursos antigos
  encapsulados por adaptadores ou usados pelo despachante legado.

## Limites conhecidos

- O planejador cobre as famílias de objetivo listadas acima; não há
  planejamento geral de qualquer pedido em linguagem natural.
- O replanejamento automático troca VS Code e IntelliJ na preparação do
  ambiente e escolhe outro nome para o resumo padrão já existente. Não há
  estratégia alternativa genérica para todas as ferramentas.
- Resultado incerto bloqueia a conclusão e não registra experiência de
  sucesso. O agente não faz automaticamente uma segunda verificação para
  todos os casos.
- Cancelamento é observado entre etapas; uma ferramenta já em execução pode
  terminar antes de o cancelamento surtir efeito.
- O motor externo pode propor sequências para frases variadas, mas suas
  propostas são validadas contra as ferramentas registradas, parâmetros e
  caminhos ditos pelo usuário. Sem ele, a composição local cobre as ações de
  projeto documentadas; não planeja execução de testes ou deploy sem ferramenta
  verificada.
- O estado da aplicação não inclui, de forma geral, janela em foco, documento
  atual ou projeto ativo. A verificação de processo ou página acessível não
  comprova que um projeto terminou de carregar.
- Inicialização, disponibilidade de MySQL, serviços locais e tempo de resposta
  dependem do ambiente. O código não garante respostas em até dois segundos
  para rede, voz ou tarefas longas.

## Testes

`tests/test_agente.py` cobre objetivo completo, replanejamento, verificação,
risco alto, cancelamento e integração com a entrada principal.
`tests/test_contrato_aplicacoes.py` cobre descoberta, ferramentas e objetivos
reais de análise/listagem com arquivos temporários.
`tests/test_configuracao_agente.py` cobre perguntas, respostas naturais,
conversa lateral, voz e persistência simulada.
`tests/test_modelo_treinavel.py` cobre 1.000 exemplos, avaliação separada,
recarregamento, treino adicional, limites de segurança e passagem real pelo
plano e verificador.
`tests/test_pedidos_dev.py` cobre variações de linguagem, composição local,
planos propostos, progresso durante execução, exportação real do Leitor e
Markdown criado e verificado pelo núcleo.
`tests/test_mysql_memoria.py`, `tests/test_memoria_disponibilidade.py` e
`tests/test_conversacao.py` cobrem memória e conversa em isolamento.

Para executar a suíte na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Os testes automatizados não substituem uma validação com microfone,
alto-falante, MySQL e aplicações gráficas reais.
