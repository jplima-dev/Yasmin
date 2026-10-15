# Desenvolvimento e manutenção

## Adicionar uma ferramenta

1. Crie uma pasta irmã de `workspace-os`, por exemplo `gerar-relatorio/`.
2. Mantenha HTML, CSS, JavaScript, testes e assets dentro dessa pasta.
3. Em cada página HTML, carregue o bootstrap global:

   ```html
   <script type="module" src="http://127.0.0.1:8790/core/module-bootstrap.js"></script>
   ```

4. Adicione uma entrada em `config/modules.json` com `id`, nome, categoria, descrição, tipo, caminho, ícone e instruções.
   Use `keywords` para sinônimos que devem aparecer no `Ctrl+K`.
5. Para uma página local, use `kind: "static-web"` e `entryFile: "index.html"`.
6. Rode os testes do Core e abra o módulo pela Home.

### Registro opcional por manifesto

Uma nova ferramenta web que esteja em uma pasta diretamente ao lado de `workspace-os/` pode entrar no catálogo sem editar o arquivo central. Crie `ink-module.json` na raiz do projeto:

```json
{
  "id": "ink-clock",
  "name": "Ink Clock",
  "description": "Relógio e fusos locais.",
  "category": "utilities",
  "kind": "static-web",
  "entryFile": "index.html",
  "icon": "clock",
  "keywords": ["hora", "fuso"],
  "version": "1.0.0"
}
```

O `id` usa letras minúsculas, números e hífens. O arquivo inicial precisa permanecer dentro da pasta do módulo. A descoberta é deliberadamente passiva: `command` e `autoStart` são rejeitados. Serviços que executam processos continuam registrados conscientemente em `config/modules.json`.
7. Teste também a URL direta e o refresh.
8. Não use `target="_blank"`: a navegação normal da suíte acontece na mesma guia.

## Usar o tema

O arquivo `../workspace-design-system/src/workspace-ui.css` é carregado pelo bootstrap em todos os módulos. Edite ali tokens e componentes que realmente pertencem a toda a suíte; use `web/core/module-theme.css` somente para adaptar seletores antigos aos tokens. Use os tokens, sem copiar cores fixas:

```css
.card {
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border);
}

.primary-button {
  color: white;
  background: var(--accent-gradient, var(--accent));
}

.primary-button:hover { background: var(--accent-hover); }
```

Tokens principais: `--background`, `--surface`, `--surface-2`, `--text`, `--text-secondary`, `--border`, `--accent`, `--accent-hover`, `--accent-soft`, `--accent-border`, `--surface-gradient`, `--hero-gradient` e `--accent-gradient`.

## Adicionar configuração global

1. Adicione o padrão em `workspace_os/settings.py` e em `web/core/settings.js`.
2. Valide tipo e valor no servidor.
3. Incremente o schema somente se houver migração necessária.
4. Aplique a preferência em `web/core/theme.js` ou no componente compartilhado responsável.
5. Na interface, use `data-global-setting="nome"`.
6. Não adicione botão Salvar: chame `Settings.set` no `input` ou `change`.
7. Teste Home e dois módulos abertos simultaneamente.

## Guardar dados de um módulo

```js
const store = Mega.storage.namespace("gerar-relatorio");
store.set("preferences", { paper: "A4" });
const preferences = store.get("preferences", { paper: "A4" });
```

Para muitos registros ou arquivos grandes, use um banco IndexedDB exclusivo, com nome baseado no módulo. Nunca reutilize o banco de outro projeto.

## Emitir eventos sem acoplamento

```js
const unsubscribe = Mega.events.on("report:exported", (event) => {
  console.log(event.detail);
});

Mega.events.emit("report:exported", { format: "pdf" });
unsubscribe();
```

Eventos são úteis dentro da mesma página. Configurações entre abas devem passar por `Mega.settings`.

Para um evento que precise aparecer em outras páginas, portas ou depois de reiniciar, use a central persistente:

```js
await Mega.activity.record({
  kind: "export",
  level: "success",
  title: "Relatório exportado",
  detail: "relatorio.pdf",
});
```

Tipos aceitos: `system`, `module`, `file`, `export`, `terminal` e `backup`. Níveis aceitos: `info`, `success`, `warning` e `error`.

## Adicionar botão ou campo

1. Use os tokens globais de cor e espaçamento.
2. Declare `type="button"` em ações comuns e `type="submit"` somente no envio real de formulário.
3. Inclua rótulo visível e estado de foco.
4. Para ação destrutiva, peça confirmação.
5. Para retorno curto, use toast; para decisão, use modal.
6. Mantenha a lógica no arquivo do módulo ou em um componente compartilhado quando houver três ou mais usos reais.

## Receber arquivos pela Drop Zone

1. Coloque um botão **Adicionar arquivo** dentro ou junto do campo que receberá o conteúdo; não transforme a página inteira em um campo invisível.
2. Mantenha um `input type="file"` com `id` estável e `accept` compatível.
3. No arquivo `web/core/dropzone.js`, adicione a extensão em `kindOf` e uma ação em `actionList` apontando para o módulo e o `id` do campo.
4. O bootstrap chama `Mega.dropzone.deliver()` automaticamente. Ele preenche o campo e dispara `change`, portanto o módulo deve reutilizar o mesmo manipulador da seleção manual.
5. Se o fluxo precisar de tratamento próprio, consulte `await Mega.dropzone.getIncoming()` antes da entrega automática.
6. Teste seleção pelo botão, arrastar sobre a página, acesso pelo `Ctrl+K`, refresh e abertura direta do módulo.

## Enviar um arquivo para outro módulo

O módulo de origem não deve importar arquivos internos do destino. Gere um `File` e use o contrato público:

```js
await Mega.dropzone.send(arquivo, {
  moduleId: "converter",
  inputId: "file-input",
});
```

Quando o destino possui uma página específica, informe um caminho servido pelo Core:

```js
await Mega.dropzone.send(imagem, {
  moduleId: "photos",
  path: "/module/photos/editor.html",
  inputId: "imageInput",
});
```

O Core armazena temporariamente o arquivo, registra a atividade, navega na mesma guia e entrega um `File` ao campo indicado. A interface de cada módulo pode chamar esse contrato por um menu **Enviar para…** sem conhecer o código interno do destino.

## Usar presets compartilhados

```js
const preset = await Mega.presets.save({
  name: "Card Instagram",
  description: "Imagem quadrada para publicação",
  moduleIds: ["photos", "converter"],
  data: { width: 1080, height: 1080, format: "webp" },
});

const presets = await Mega.presets.list({ moduleId: "photos" });
await Mega.presets.remove(preset.id);
```

O Core guarda apenas JSON pequeno e não interpreta os campos de `data`. Cada módulo decide como aplicar o preset, mantendo o acoplamento somente pelo contrato público.

## Usar o clipboard interno

```js
await Mega.clipboard.add("Texto criado no módulo", { source: "mini-word" });
const itens = await Mega.clipboard.list();
await Mega.clipboard.copy(itens[0]);
await Mega.clipboard.pin(itens[0].id, true);
```

O clipboard interno é textual, persiste no Core e aparece na central `♢`. Ele não lê silenciosamente a área de transferência do Windows; copiar para o sistema continua exigindo uma ação do usuário.

## Incluir dados de um módulo no backup portátil

O Core não percorre bancos IndexedDB arbitrariamente. O módulo registra um contrato explícito:

```js
const backup = Mega.backup.register({
  moduleId: "mini-word",
  schemaVersion: 1,
  async exportData() {
    return { documents: await listDocuments() };
  },
  async importData(data) {
    await replaceDocuments(data.documents || []);
  },
});

await backup.publish();
// Quando o usuário estiver restaurando dentro do módulo:
await backup.restore();
```

O snapshot tem limite de 8 MiB e fica isolado pelo ID. Alterar o schema exige migração dentro de `importData`.

## Manifesto, compatibilidade e permissões

Manifestos opcionais aceitam `version`, `minCoreVersion` e `permissions`. Use permissões descritivas como `files:read`, `network:local` ou `terminal`; elas aparecem na Central e documentam a superfície necessária. Módulos descobertos não podem definir `command` nem `autoStart`.

## Testar a integração

1. Inicie o Workspace OS e aguarde a Home aparecer.
2. Na barra lateral, abra **Configurações → Aparência**.
3. Troque o tema, a cor livre e o idioma; cada mudança deve aparecer imediatamente, sem botão Salvar.
4. Volte à Home e abra InkWrite. Confirme que ele substitui a Home na mesma guia e mantém as preferências.
5. Use **← Workspace** para retornar e repita com InkSheet.
6. Para testar várias abas, mantenha a Home aberta e cole a URL direta de InkWrite em uma segunda aba e a de InkSheet em uma terceira.
7. Altere tema, cor e idioma em uma das abas e confirme a atualização nas demais.
8. Feche todas as abas, abra novamente e confirme a persistência.
9. Atualize cada URL direta e confirme que o módulo carrega e retorna à Home.
10. Execute os testes específicos da pasta alterada; não é necessário modificar os demais módulos.
11. Arraste um JSON para qualquer página, escolha **Visualizar e editar** e confirme que o Ink JSON abre na mesma guia com o conteúdo carregado.
12. Abra o terminal em um módulo, clique fora do painel e confirme que ele fecha.
