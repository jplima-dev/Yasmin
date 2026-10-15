import { Activity } from "./activity.js";
import { Settings } from "./settings.js";
import { apiRequest, authorizedFetch, CORE_ORIGIN, coreUrl } from "./origin.js";

const STYLE_URL = `${CORE_ORIGIN}/core/dropzone.css`;
const FALLBACK_CHUNK_SIZE = 8 * 1024 * 1024;

function ensureStyles() {
  if (document.querySelector(`link[href="${STYLE_URL}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_URL;
  document.head.append(link);
}

async function api(path, options = {}) {
  return apiRequest(path, options);
}

export async function storeDropFile(file, {
  kind = "file", name = file?.name || "pasta", folderId = "", relativePath = "", onProgress,
} = {}) {
  if (kind === "folder") return createDropFolder({ name, files: 0, size: 0 });
  if (!(file instanceof Blob)) throw new TypeError("Envie um arquivo válido.");
  const upload = await api("/api/dropzone/uploads", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name, type: file.type || "application/octet-stream", size: file.size,
      lastModified: file.lastModified || 0, folderId, relativePath: relativePath || file.webkitRelativePath || name,
    }),
  });
  const chunkSize = Number(upload.chunkSize) || FALLBACK_CHUNK_SIZE;
  let offset = Number(upload.offset) || 0;
  try {
    onProgress?.({ loaded: offset, total: file.size, name });
    while (offset < file.size) {
      const chunk = file.slice(offset, Math.min(file.size, offset + chunkSize));
      const response = await authorizedFetch(`/api/dropzone/uploads/${encodeURIComponent(upload.uploadId)}/chunk`, {
        method: "POST", headers: { "Content-Type": "application/octet-stream", "X-Upload-Offset": String(offset) }, body: chunk,
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || `Falha ao enviar bloco (${response.status}).`);
      offset = Number(result.offset);
      onProgress?.({ loaded: offset, total: file.size, name });
    }
    return await api(`/api/dropzone/uploads/${encodeURIComponent(upload.uploadId)}/complete`, { method: "POST" });
  } catch (error) {
    await authorizedFetch(`/api/dropzone/uploads/${encodeURIComponent(upload.uploadId)}`, { method: "DELETE" }).catch(() => {});
    throw error;
  }
}

export async function createDropFolder({ name, files, size }) {
  return api("/api/dropzone/folders", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, fileCount: files, size }),
  });
}

export async function getDropHistory() {
  return (await api("/api/dropzone/history")).items || [];
}

export async function getDropItem(itemId) {
  const response = await authorizedFetch(`/api/dropzone/files/${encodeURIComponent(itemId)}/content`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Não foi possível recuperar o arquivo (${response.status}).`);
  const encodedName = response.headers.get("X-File-Name") || "arquivo";
  let name = encodedName;
  try { name = decodeURIComponent(encodedName); } catch { /* mantém fallback legível */ }
  const blob = await response.blob();
  return { id: itemId, name, type: blob.type, size: blob.size, file: new File([blob], name, { type: blob.type }) };
}

function remoteFolderFile(folderId, item) {
  const url = coreUrl(`/api/dropzone/folders/${encodeURIComponent(folderId)}/files/${encodeURIComponent(item.id)}/content`);
  const readRange = async (start = 0, end = item.size) => {
    if (end <= start) return new ArrayBuffer(0);
    const response = await authorizedFetch(url, { headers: { Range: `bytes=${start}-${end - 1}` }, cache: "no-store" });
    if (!response.ok) throw new Error(`Não foi possível ler ${item.path} (${response.status}).`);
    return response.arrayBuffer();
  };
  return {
    name: item.name, type: item.type || "application/octet-stream", size: item.size,
    lastModified: item.lastModified || 0, webkitRelativePath: item.path,
    slice: (start = 0, end = item.size) => ({ arrayBuffer: () => readRange(start, end) }),
    arrayBuffer: () => readRange(0, item.size),
    text: async () => new TextDecoder().decode(await readRange(0, item.size)),
  };
}

export async function getDropFolder(itemId) {
  const manifest = await api(`/api/dropzone/folders/${encodeURIComponent(itemId)}`);
  return { ...manifest, files: (manifest.files || []).map((item) => remoteFolderFile(itemId, item)) };
}

export async function getIncomingDrop(search = location.search) {
  const itemId = new URLSearchParams(search).get("workspaceDrop");
  return itemId ? getDropItem(itemId) : null;
}

function removeDeliveryParams() {
  const url = new URL(location.href);
  url.searchParams.delete("workspaceDrop");
  url.searchParams.delete("workspaceInput");
  history.replaceState(history.state, "", url);
}

export async function deliverIncomingDrop() {
  const params = new URLSearchParams(location.search);
  const itemId = params.get("workspaceDrop");
  if (!itemId) return null;
  const incoming = await getDropItem(itemId);
  const requestedId = params.get("workspaceInput");
  let input = requestedId ? document.getElementById(requestedId) : null;
  for (let attempt = 0; !input && attempt < 30; attempt += 1) {
    input = document.querySelector('input[type="file"]');
    if (!input) await new Promise((resolve) => setTimeout(resolve, 100));
  }
  if (!input) return incoming;
  const transfer = new DataTransfer();
  transfer.items.add(incoming.file);
  input.files = transfer.files;
  input.dispatchEvent(new Event("change", { bubbles: true }));
  removeDeliveryParams();
  return incoming;
}

export async function sendDropFile(file, { moduleId, inputId = "", path = "" } = {}) {
  if (!(file instanceof File)) throw new TypeError("Envie um arquivo válido.");
  if (!moduleId) throw new Error("Informe o módulo de destino.");
  const modules = (await api("/api/modules")).modules || [];
  const module = modules.find((item) => item.id === moduleId);
  if (!module?.url) throw new Error("O módulo de destino não possui um endereço disponível.");
  const stored = await storeDropFile(file);
  const base = path ? `${CORE_ORIGIN}${path}` : module.url;
  const url = withDrop(base, stored, inputId);
  await Activity.record({
    kind: "file", level: "success", moduleId,
    title: `Enviado para ${module.name}`,
    detail: file.name,
    url,
  }).catch(() => {});
  location.assign(url);
  return stored;
}

function extensionOf(name) {
  const match = String(name).toLocaleLowerCase("pt-BR").match(/\.([a-z0-9]+)$/);
  return match ? match[1] : "";
}

function kindOf(item) {
  if (item.kind === "folder") return "folder";
  const extension = extensionOf(item.name);
  if (item.type?.startsWith("image/") || ["png","jpg","jpeg","webp","gif","bmp","heic","heif","svg"].includes(extension)) return "image";
  if (extension === "pdf" || item.type === "application/pdf") return "pdf";
  if (extension === "json" || item.type?.includes("json")) return "json";
  if (["csv","tsv"].includes(extension)) return "csv";
  if (["txt","md","markdown","html","htm","css","js","mjs","cjs","ts","tsx","jsx","py","java","c","cpp","h","hpp","cs","php","rb","go","rs","sql","xml","yaml","yml","toml","ini","env","log","sh","ps1","bat","cmd"].includes(extension) || item.type?.startsWith("text/")) return "text";
  return "other";
}

function withDrop(url, item, inputId) {
  const target = new URL(url, location.href);
  target.searchParams.set("workspaceDrop", item.id);
  if (inputId) target.searchParams.set("workspaceInput", inputId);
  return target.href;
}

function withFolder(url, item) {
  const target = new URL(url, location.href);
  target.searchParams.set("workspaceFolder", item.id);
  return target.href;
}

function actionList(item, modules, associations = {}) {
  const modulesById = new Map(modules.map((module) => [module.id, module]));
  const moduleAction = (id, label, { path, inputId } = {}) => {
    const module = modulesById.get(id);
    if (!module?.url) return null;
    const url = path ? `${CORE_ORIGIN}${path}` : module.url;
    return { label, moduleId: id, run: () => location.assign(item.kind === "folder" ? withFolder(url, item) : withDrop(url, item, inputId)) };
  };
  const kind = kindOf(item);
  let actions = [];
  if (kind === "folder") actions = [moduleAction("project-analyzer", "Analisar projeto")];
  if (kind === "image") actions = [
    moduleAction("photos", "Editar foto", { path: "/module/photos/editor.html", inputId: "imageInput" }),
    moduleAction("converter", "Converter", { inputId: "file-input" }),
    moduleAction("base64", "Gerar Data URL", { inputId: "file-input" }),
  ];
  if (kind === "json") actions = [
    moduleAction("json", "Visualizar e editar", { inputId: "file-input" }),
    moduleAction("converter", "Converter", { inputId: "file-input" }),
    moduleAction("base64", "Codificar Base64", { inputId: "file-input" }),
  ];
  if (kind === "csv") actions = [
    moduleAction("sheets", "Abrir no InkSheet", { path: "/module/sheets/editor.html", inputId: "csvFileInput" }),
    moduleAction("converter", "Converter", { inputId: "file-input" }),
    moduleAction("diff", "Comparar como texto", { inputId: "before-file" }),
  ];
  if (kind === "text") actions = [
    moduleAction("writer", "Criar documento", { path: "/module/writer/editor.html", inputId: "projectInput" }),
    moduleAction("diff", "Comparar texto", { inputId: "before-file" }),
    moduleAction("base64", "Codificar Base64", { inputId: "file-input" }),
    moduleAction("project-reader", "Abrir Leitor de Projetos"),
  ];
  if (kind === "pdf") actions = [
    { label: "Visualizar PDF", run: async () => { const incoming = await getDropItem(item.id); location.assign(URL.createObjectURL(incoming.file)); } },
    moduleAction("base64", "Codificar Base64", { inputId: "file-input" }),
  ];
  if (kind === "other") actions = [moduleAction("base64", "Abrir no Ink Base64", { inputId: "file-input" })];
  if (kind !== "folder") actions.push(moduleAction("drive2", "Salvar no InkDriver", { inputId: "uploadInput" }));
  const preferred = associations[extensionOf(item.name)];
  return actions.filter(Boolean).sort((left, right) => Number(right.moduleId === preferred) - Number(left.moduleId === preferred)).slice(0, 5);
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes, unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value.toFixed(unit ? 1 : 0)} ${units[unit]}`;
}

function markup() {
  return `
    <button class="workspace-drop-launcher" type="button" aria-label="Abrir Drop Zone" title="Abrir Drop Zone">⇩</button>
    <section class="workspace-drop-panel" aria-label="Drop Zone universal" hidden>
      <header><div><strong>Drop Zone</strong><span>Abra arquivos no módulo certo</span></div><button type="button" data-drop-close aria-label="Fechar">×</button></header>
      <div class="workspace-drop-add">
        <label class="workspace-drop-add-button">＋ Adicionar arquivos<input type="file" data-drop-files multiple></label>
        <label class="workspace-drop-add-button secondary">▣ Escolher pasta<input type="file" data-drop-folder webkitdirectory></label>
      </div>
      <div class="workspace-drop-status" role="status">Arraste arquivos em qualquer parte da tela.</div>
      <div class="workspace-drop-history"></div>
    </section>
    <div class="workspace-drop-overlay" hidden><div><span>⇩</span><strong>Solte na Drop Zone</strong><small>O Workspace identifica o tipo e mostra as ações disponíveis.</small></div></div>`;
}

export function mountUniversalDropzone({ target = document.body } = {}) {
  if (document.querySelector(".workspace-drop-launcher")) return null;
  ensureStyles();
  const host = document.createElement("div");
  host.className = "workspace-drop-host";
  host.innerHTML = markup();
  target.append(host);
  const launcher = host.querySelector(".workspace-drop-launcher");
  const panel = host.querySelector(".workspace-drop-panel");
  const overlay = host.querySelector(".workspace-drop-overlay");
  const historyRoot = host.querySelector(".workspace-drop-history");
  const status = host.querySelector(".workspace-drop-status");
  let modules = [];
  let associations = {};
  let dragDepth = 0;

  function open() { panel.hidden = false; launcher.setAttribute("aria-expanded", "true"); launcher.blur(); renderHistory(); }
  function close() { panel.hidden = true; launcher.setAttribute("aria-expanded", "false"); launcher.blur(); }
  function setStatus(message, tone = "") { status.textContent = message; status.dataset.tone = tone; }

  async function loadModules() {
    if (modules.length) return modules;
    try {
      [modules] = await Promise.all([
        api("/api/modules").then((payload) => payload.modules || []),
        Settings.init().then(() => { associations = Settings.get("file_associations") || {}; }),
      ]);
    } catch { modules = []; }
    return modules;
  }

  async function renderHistory() {
    const [items] = await Promise.all([getDropHistory(), loadModules()]);
    historyRoot.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("div"); empty.className = "workspace-drop-empty"; empty.textContent = "Nenhum arquivo recebido ainda."; historyRoot.append(empty); return;
    }
    for (const item of items.slice(0, 10)) {
      const card = document.createElement("article"); card.className = "workspace-drop-item";
      const icon = document.createElement("span"); icon.className = "workspace-drop-icon"; icon.textContent = item.kind === "folder" ? "▣" : (extensionOf(item.name).slice(0,4).toUpperCase() || "FILE");
      const copy = document.createElement("div"); copy.className = "workspace-drop-copy";
      const name = document.createElement("strong"); name.textContent = item.name;
      const folderMeta = item.kind === "folder" ? `${item.receivedFiles || 0}/${item.fileCount || 0} arquivos · ` : "";
      const meta = document.createElement("small"); meta.textContent = `${kindOf(item)} · ${folderMeta}${formatBytes(item.size)} · ${new Date(item.createdAt).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}`;
      copy.append(name, meta);
      const buttons = document.createElement("div"); buttons.className = "workspace-drop-actions";
      const compatible = actionList(item, modules, associations);
      for (const action of compatible) {
        const button = document.createElement("button"); button.type = "button";
        button.textContent = action.moduleId === associations[extensionOf(item.name)] ? `★ ${action.label}` : action.label;
        button.addEventListener("click", async () => { try { await action.run(); } catch (error) { setStatus(error.message, "error"); } });
        buttons.append(button);
      }
      const extension = extensionOf(item.name);
      const destinations = compatible.filter((action) => action.moduleId);
      if (extension && destinations.length > 1) {
        const association = document.createElement("select");
        association.className = "workspace-drop-association";
        association.setAttribute("aria-label", `Aplicativo padrão para .${extension}`);
        association.innerHTML = `<option value="">Sempre perguntar para .${extension}</option>${destinations.map((action) => `<option value="${action.moduleId}">${action.label}</option>`).join("")}`;
        association.value = associations[extension] || "";
        association.addEventListener("change", async () => {
          associations = { ...associations };
          if (association.value) associations[extension] = association.value; else delete associations[extension];
          await Settings.set("file_associations", associations);
          setStatus(association.value ? `.${extension} agora abre primeiro em ${association.selectedOptions[0].textContent}.` : `Associação de .${extension} removida.`, "success");
          await renderHistory();
        });
        buttons.append(association);
      }
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "workspace-drop-remove";
      remove.setAttribute("aria-label", `Remover ${item.name} do histórico`); remove.title = "Remover do histórico"; remove.textContent = "×";
      remove.addEventListener("click", async () => {
        try {
          await api(`/api/dropzone/files/${encodeURIComponent(item.id)}`, { method: "DELETE" });
          await renderHistory();
        } catch (error) { setStatus(error.message, "error"); }
      });
      card.append(icon, copy, remove, buttons); historyRoot.append(card);
    }
  }

  async function receiveFiles(files) {
    const selected = [...files];
    if (!selected.length) return;
    open(); setStatus(`Recebendo ${selected.length} arquivo(s)…`);
    let saved = 0;
    for (const [index, file] of selected.entries()) {
      try {
        await storeDropFile(file, { onProgress: ({ loaded, total }) => setStatus(`Arquivo ${index + 1}/${selected.length} · ${file.name} · ${formatBytes(loaded)}/${formatBytes(total)}`) });
        saved += 1;
      }
      catch (error) { setStatus(`${file.name}: ${error.message}`, "error"); }
    }
    if (saved) setStatus(`${saved} arquivo(s) prontos. Escolha uma ação.`, "success");
    if (saved) Activity.record({ kind: "file", level: "success", title: `${saved} arquivo(s) adicionados à Drop Zone`, detail: selected.slice(0, 3).map((file) => file.name).join(", ") }).catch(() => {});
    await renderHistory();
  }

  async function receiveFolder(files, requestedName = "") {
    const entries = [...files].map((entry) => entry?.file ? entry : ({ file: entry, path: entry.webkitRelativePath || entry.name }));
    if (!entries.length) return;
    const folderName = requestedName || entries[0].path?.split("/")[0] || "Pasta selecionada";
    const totalSize = entries.reduce((sum, entry) => sum + Number(entry.file?.size || 0), 0);
    open(); setStatus(`Preparando ${entries.length} arquivo(s)…`);
    const folder = await createDropFolder({ name: folderName, files: entries.length, size: totalSize });
    let completedBytes = 0;
    let saved = 0;
    for (const [index, entry] of entries.entries()) {
      try {
        await storeDropFile(entry.file, {
          folderId: folder.id, relativePath: entry.path,
          onProgress: ({ loaded }) => setStatus(`Pasta ${index + 1}/${entries.length} · ${formatBytes(completedBytes + loaded)}/${formatBytes(totalSize)}`),
        });
        completedBytes += entry.file.size;
        saved += 1;
      } catch (error) { setStatus(`${entry.path}: ${error.message}`, "error"); }
    }
    await api(`/api/dropzone/folders/${encodeURIComponent(folder.id)}/complete`, { method: "POST" });
    Activity.record({ kind: "file", level: saved === entries.length ? "success" : "warning", title: "Pasta adicionada à Drop Zone", detail: `${folderName} · ${saved}/${entries.length} arquivos` }).catch(() => {});
    setStatus(`${saved}/${entries.length} arquivo(s) prontos. Abra no Analisador de Projetos.`, saved === entries.length ? "success" : "error");
    await renderHistory();
  }

  async function readDroppedEntry(entry, prefix = "") {
    if (entry.isFile) {
      const file = await new Promise((resolve, reject) => entry.file(resolve, reject));
      return [{ file, path: `${prefix}${file.name}` }];
    }
    if (!entry.isDirectory) return [];
    const reader = entry.createReader();
    const children = [];
    for (;;) {
      const batch = await new Promise((resolve, reject) => reader.readEntries(resolve, reject));
      if (!batch.length) break;
      children.push(...batch);
    }
    const nested = [];
    for (const child of children) nested.push(...await readDroppedEntry(child, `${prefix}${entry.name}/`));
    return nested;
  }

  launcher.addEventListener("click", () => panel.hidden ? open() : close());
  host.querySelector("[data-drop-close]").addEventListener("click", close);
  host.querySelector("[data-drop-files]").addEventListener("change", (event) => { receiveFiles(event.target.files); event.target.value = ""; });
  host.querySelector("[data-drop-folder]").addEventListener("change", (event) => { receiveFolder(event.target.files); event.target.value = ""; });
  document.addEventListener("pointerdown", (event) => { if (!panel.hidden && !panel.contains(event.target) && !launcher.contains(event.target)) close(); });
  document.addEventListener("dragenter", (event) => { if (![...event.dataTransfer?.types || []].includes("Files")) return; event.preventDefault(); dragDepth += 1; overlay.hidden = false; });
  document.addEventListener("dragover", (event) => { if ([...event.dataTransfer?.types || []].includes("Files")) event.preventDefault(); });
  document.addEventListener("dragleave", (event) => { if (![...event.dataTransfer?.types || []].includes("Files")) return; dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) overlay.hidden = true; });
  document.addEventListener("drop", async (event) => {
    if (![...event.dataTransfer?.types || []].includes("Files")) return;
    event.preventDefault(); dragDepth = 0; overlay.hidden = true;
    const entries = [...event.dataTransfer.items || []].map((item) => item.webkitGetAsEntry?.()).filter(Boolean);
    const folder = entries.find((entry) => entry.isDirectory);
    if (folder) {
      try { await receiveFolder(await readDroppedEntry(folder), folder.name); }
      catch (error) { open(); setStatus(`Não foi possível ler a pasta: ${error.message}`, "error"); }
      return;
    }
    const files = [...event.dataTransfer.files || []];
    if (files.length) await receiveFiles(files);
  });
  loadModules();
  return Object.freeze({ open, close, refresh: renderHistory, receiveFiles, send: sendDropFile, element: panel });
}
