# Contrato de integração com a Yasmin

Cada aplicação conserva seu próprio código, dados, licença e funcionamento independente. O arquivo `ink-module.json` existente é a fonte de identidade e recursos. Na integração com a Yasmin, `vendor` e `author` identificam **Ink-guginha**. Créditos e copyright já presentes continuam intactos.

`capabilities` descreve recursos gerais da interface. Um recurso como `export: true` não autoriza o agente a exportar dados automaticamente. Operações utilizáveis pelo Agent Core devem ser declaradas separadamente em `agentOperations`:

```json
{
  "vendor": "Ink-guginha",
  "author": "Ink-guginha",
  "agentOperations": [
    {
      "name": "nome_unico_da_ferramenta",
      "description": "Ação real exposta pela aplicação",
      "parameters": ["parametro_obrigatorio"],
      "risk": "baixo",
      "verification": "verificador_registrado"
    }
  ]
}
```

`risk` usa `baixo`, `medio` ou `alto`. A operação só é registrada quando existir um adapter explícito e um verificador no Agent Core. O manifesto não pode fornecer código, comandos ou URL arbitrária para execução. Resultados usam `ResultadoFerramenta`; evidências usam `ResultadoVerificacao`. O estado operacional permanece na aplicação e é observado seletivamente pela `Percepcao` da Yasmin.

As interfaces gráficas permanecem nas aplicações. O pedido “Yasmin, abra a Workspace” ou “abra o Ink JSON” é resolvido pela identidade do manifesto. A ferramenta `abrir_aplicacao_ink` consulta o registro existente do Workspace OS, abre o endereço da interface no navegador e verifica se a página local responde. Serviços com comando declarado são iniciados pelo Workspace OS, que mantém seu controle de confiança e sessão. Essa ferramenta não substitui as operações próprias de cada aplicação.

Para serviços como o Ink Notebook, a moldura HTML sozinha não comprova funcionamento: a abertura também exige que a URL de saúde da aplicação responda. A operação `listar_cadernos_ink` usa `GET /api/notebooks`, devolve somente identificadores, nomes e contagens atuais e verifica a lista novamente. O banco operacional do Notebook não é copiado para a memória pessoal da Yasmin.

O Leitor de Projetos declara `listar_arquivos_projeto_ink`. O adapter chama a classificação pública do aplicativo em um processo Python isolado, usa as preferências e os filtros originais, e devolve contagens e até 20 caminhos relativos. Não lê o conteúdo dos arquivos, não exporta nada e não retorna nomes identificados como sensíveis. A verificação repete a classificação. Sua interface gráfica continua abrindo pelo Workspace OS.

## Estado de integração verificado

- A descoberta encontra 16 aplicações: 15 manifestos e o Workspace OS. Todos os manifestos declaram `Ink-guginha` como fornecedor e autor. As licenças originais são preservadas.
- As 16 interfaces podem ser solicitadas pelo nome. O Workspace OS é a infraestrutura compartilhada para servir páginas e iniciar serviços locais.
- Operações adicionais comprovadas: análise de projeto, listagem de cadernos do Ink Notebook e classificação de arquivos do Leitor de Projetos. As demais aplicações têm abertura e consulta de disponibilidade, mas ainda não declaram operações de dados para o agente.
- O Organizador guarda projetos no IndexedDB do perfil do navegador e não expõe uma API de consulta. O pedido de abrir a interface do Organizador funciona; abrir um registro interno pelo nome ainda exige uma interface programática confiável e identificação do projeto.
- O Ink Terminal declara execução irrestrita de PowerShell. A integração não registra essa execução como ferramenta automática, pois exigiria classificação e confirmação de risco alto.
- A verificação de abertura comprova que o serviço e a página local respondem e que o sistema aceitou a abertura do navegador. A API atual não confirma que a janela ficou em primeiro plano. Inícios a frio de serviços podem ultrapassar dois segundos; isso não é mascarado como garantia de latência.
