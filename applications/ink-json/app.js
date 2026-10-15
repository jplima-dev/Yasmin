const editor = document.querySelector("#editor");
const tree = document.querySelector("#tree");
const status = document.querySelector("#status");
const search = document.querySelector("#search");
let parsedValue;
let currentName = "dados.json";

function setStatus(message, tone = "") {
  status.textContent = message;
  status.className = `tool-status ${tone}`.trim();
}

function parseEditor({ quiet = false } = {}) {
  try {
    parsedValue = JSON.parse(editor.value);
    const bytes = new Blob([editor.value]).size;
    const rootType = Array.isArray(parsedValue) ? `array com ${parsedValue.length} itens` : typeof parsedValue;
    if (!quiet) setStatus(`JSON válido · ${rootType} · ${bytes.toLocaleString("pt-BR")} bytes`, "success");
    renderTree();
    return true;
  } catch (error) {
    parsedValue = undefined;
    tree.innerHTML = '<span class="tree-meta">Corrija o JSON para visualizar a árvore.</span>';
    if (!quiet) setStatus(`JSON inválido: ${error.message}`, "error");
    return false;
  }
}

function primitiveClass(value) {
  if (value === null) return "tree-null";
  return `tree-${typeof value}`;
}

function renderTree() {
  tree.replaceChildren();
  const query = search.value.trim().toLocaleLowerCase("pt-BR");
  let nodes = 0;
  const limit = 10_000;

  function createNode(value, key, depth, parentIsArray = false) {
    nodes += 1;
    if (nodes > limit) {
      const capped = document.createElement("div");
      capped.className = "tree-meta";
      capped.textContent = "… visualização limitada a 10.000 nós";
      return capped;
    }
    const container = document.createElement("div");
    container.className = depth ? "tree-node" : "";
    const row = document.createElement("div");
    row.className = "tree-row";
    const searchable = `${key ?? ""} ${typeof value === "object" ? "" : String(value)}`.toLocaleLowerCase("pt-BR");
    if (query && searchable.includes(query)) row.classList.add("match");

    const isGroup = value !== null && typeof value === "object";
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "tree-toggle";
    toggle.textContent = isGroup ? "▾" : "";
    row.append(toggle);
    if (key !== null) {
      const keyElement = document.createElement("span");
      keyElement.className = "tree-key";
      keyElement.textContent = parentIsArray ? `[${key}]` : String(key);
      row.append(keyElement, document.createTextNode(": "));
    }
    if (isGroup) {
      const meta = document.createElement("span");
      meta.className = "tree-meta";
      const entries = Object.entries(value);
      meta.textContent = Array.isArray(value) ? `Array(${entries.length})` : `Object(${entries.length})`;
      row.append(meta);
      const children = document.createElement("div");
      for (const [childKey, childValue] of entries) children.append(createNode(childValue, childKey, depth + 1, Array.isArray(value)));
      toggle.addEventListener("click", () => {
        children.hidden = !children.hidden;
        toggle.textContent = children.hidden ? "▸" : "▾";
      });
      container.append(row, children);
    } else {
      const valueElement = document.createElement("span");
      valueElement.className = primitiveClass(value);
      valueElement.textContent = typeof value === "string" ? JSON.stringify(value) : String(value);
      row.append(valueElement);
      container.append(row);
    }
    return container;
  }

  tree.append(createNode(parsedValue, null, 0));
}

document.querySelector("#validate").addEventListener("click", () => parseEditor());
document.querySelector("#format").addEventListener("click", () => {
  if (!parseEditor()) return;
  editor.value = JSON.stringify(parsedValue, null, 2);
  parseEditor();
});
document.querySelector("#minify").addEventListener("click", () => {
  if (!parseEditor()) return;
  editor.value = JSON.stringify(parsedValue);
  parseEditor();
});
document.querySelector("#copy").addEventListener("click", async () => {
  if (!parseEditor({ quiet: true })) return setStatus("Não há JSON válido para copiar.", "error");
  try { await navigator.clipboard.writeText(editor.value); setStatus("JSON copiado.", "success"); }
  catch { setStatus("Não foi possível copiar.", "error"); }
});
document.querySelector("#download").addEventListener("click", () => {
  if (!parseEditor()) return;
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([editor.value], { type: "application/json" }));
  link.download = currentName.endsWith(".json") ? currentName : `${currentName}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 0);
});
document.querySelector("#sample").addEventListener("click", () => {
  editor.value = JSON.stringify({ projeto: "Ink", versao: 1, ativo: true, modulos: ["Ink JSON", "Ink Palette", "Ink Diff"], configuracao: { tema: "global", armazenamento: "local" } }, null, 2);
  currentName = "exemplo-ink.json";
  parseEditor();
});
document.querySelector("#file-input").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  currentName = file.name;
  editor.value = await file.text();
  parseEditor();
  event.target.value = "";
});
search.addEventListener("input", () => { if (parsedValue !== undefined) renderTree(); });
editor.addEventListener("input", () => setStatus("Conteúdo alterado; valide para atualizar a árvore."));

document.querySelector("#sample").click();
