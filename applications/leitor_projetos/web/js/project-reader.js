export const DEFAULTS = Object.freeze({
  singleExtensions: [".php", ".css", ".js", ".py", ".html", ".txt", ".bat", ".md"],
  separateExtensions: [".php", ".css", ".js"],
  ignoredFolders: ["vendor", "node_modules", ".git", "__pycache__", ".venv", "venv", "env", "Lib", "Include", "Scripts", ".idea", ".vscode"],
  ignoredFiles: [".env", ".gitignore"],
});

const SENSITIVE_EXACT = new Set([
  ".env", ".env.local", ".env.development", ".env.production", ".env.test",
  "credentials.json", "secrets.json", "id_rsa", "id_rsa.pub", "id_ed25519"
]);
const SENSITIVE_SUBSTRINGS = ["secret", "senha", "password", "token", "apikey", "api_key", "credential"];

const LANGUAGE_BY_EXTENSION = new Map([
  ["js", "javascript"], ["jsx", "jsx"], ["ts", "typescript"], ["tsx", "tsx"],
  ["py", "python"], ["html", "html"], ["css", "css"], ["scss", "scss"],
  ["json", "json"], ["md", "markdown"], ["sql", "sql"], ["sh", "bash"],
  ["ps1", "powershell"], ["yaml", "yaml"], ["yml", "yaml"], ["xml", "xml"],
  ["php", "php"], ["java", "java"], ["kt", "kotlin"], ["c", "c"], ["cpp", "cpp"],
  ["h", "c"], ["hpp", "cpp"], ["cs", "csharp"], ["go", "go"], ["rs", "rust"],
  ["rb", "ruby"], ["swift", "swift"], ["dart", "dart"], ["lua", "lua"],
  ["r", "r"], ["vue", "vue"], ["svelte", "svelte"], ["astro", "astro"],
  ["bat", "bat"], ["cmd", "bat"], ["toml", "toml"], ["ini", "ini"], ["cfg", "ini"],
  ["txt", "text"], ["csv", "text"]
]);

const isWindowsAbsolute = (value) => /^[a-z]:\//i.test(value) || value.startsWith("//");

export function parseLines(value) {
  return String(value ?? "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

export function normalizeExtension(value) {
  const v = String(value ?? "").trim().toLowerCase();
  if (!v) return "";
  return v.startsWith(".") ? v : `.${v}`;
}

export function parseExtensions(value) {
  return parseLines(String(value ?? "").replace(/[;,]+/g, "\n"))
    .map(normalizeExtension)
    .filter(Boolean);
}

export function safeName(value) {
  return String(value || "projeto")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase() || "projeto";
}

export function extensionOf(name) {
  const index = name.lastIndexOf(".");
  return index > 0 ? name.slice(index) : "";
}

export function languageOf(name) {
  return LANGUAGE_BY_EXTENSION.get(extensionOf(name).slice(1).toLowerCase()) || "";
}

export function estimateTokens(text) {
  return Math.ceil(String(text ?? "").length / 4);
}

export function isSensitiveName(name) {
  const lower = String(name).toLowerCase();
  return SENSITIVE_EXACT.has(lower)
    || lower.startsWith(".env.")
    || lower.endsWith(".pem")
    || SENSITIVE_SUBSTRINGS.some((pattern) => lower.includes(pattern));
}

export function normalizeRelativePath(path) {
  return String(path ?? "").replace(/\\/g, "/").replace(/^\.\/+/, "").replace(/^\/+/, "").replace(/\/+/g, "/");
}

export class IgnoreFilter {
  constructor(rules = []) {
    this.names = new Set();
    this.paths = new Set();
    for (const raw of rules) {
      const value = String(raw ?? "").trim().replace(/\\/g, "/");
      if (!value) continue;
      if (!value.includes("/") && !isWindowsAbsolute(value)) {
        this.names.add(value.toLowerCase());
      } else if (!isWindowsAbsolute(value)) {
        this.paths.add(normalizeRelativePath(value).toLowerCase().replace(/\/+$/, ""));
      } else {
        this.paths.add(value.toLowerCase().replace(/\/+$/, ""));
      }
    }
  }

  matches(relativePath) {
    const path = normalizeRelativePath(relativePath);
    const lower = path.toLowerCase();
    const base = lower.split("/").pop();
    return this.names.has(base) || this.paths.has(lower);
  }
}

function canReadText(buffer) {
  const bytes = new Uint8Array(buffer);
  return !bytes.includes(0);
}

async function readUtf8Text(file) {
  const buffer = await file.arrayBuffer();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  const text = decoder.decode(buffer);
  if (!canReadText(buffer)) {
    throw new Error("Arquivo não é texto legível (possível binário).");
  }
  return text;
}

function createContext({ extensions, ignoredFolders, ignoredFiles, selectedPaths = null, mode = "single" }) {
  return {
    extensions: new Set(extensions),
    ignoredFolders: new IgnoreFilter(ignoredFolders),
    ignoredFiles: new IgnoreFilter(ignoredFiles),
    selectedPaths: selectedPaths ? new Set([...selectedPaths].map(normalizeRelativePath)) : null,
    files: [],
    entries: [],
    warnings: [],
    errors: [],
    sensitive: 0,
    mode
  };
}

function folderState(c, path) {
  if (c.ignoredFolders.matches(path)) return "ignored";
  return "folder";
}

async function directoryHasMarker(handle, markerName = ".leitor-ia") {
  try {
    await handle.getFileHandle(markerName);
    return true;
  } catch {
    return false;
  }
}

async function ingestFile(c, path, name, getFile) {
  if (isSensitiveName(name)) {
    c.sensitive += 1;
    c.entries.push({ path, name, kind: "file", state: "blocked", size: 0, depth: path.split("/").length - 1 });
    return;
  }

  if (c.ignoredFiles.matches(path)) {
    c.entries.push({ path, name, kind: "file", state: "ignored", size: 0, depth: path.split("/").length - 1 });
    return;
  }

  const allowed = [...c.extensions].some((extension) => name.toLowerCase().endsWith(extension.toLowerCase()));
  if (!allowed) {
    c.entries.push({ path, name, kind: "file", state: "blocked", size: 0, depth: path.split("/").length - 1 });
    return;
  }

  try {
    const file = await getFile();
    const buffer = await file.arrayBuffer();
    const decoder = new TextDecoder("utf-8", { fatal: true });
    const content = decoder.decode(buffer);
    if (!canReadText(buffer)) throw new Error("Arquivo não é texto legível (possível binário).");

    const selected = !c.selectedPaths || c.selectedPaths.has(normalizeRelativePath(path));
    const record = {
      path: normalizeRelativePath(path),
      name,
      size: Number(file.size || buffer.byteLength || 0),
      text: content,
      language: languageOf(name),
      selected,
    };
    c.files.push(record);
    c.entries.push({
      ...record,
      kind: "file",
      state: selected ? "included" : "not-selected",
      depth: path.split("/").length - 1
    });
  } catch (error) {
    const reason = error?.message || String(error);
    c.errors.push(`${path}: ${reason}`);
    c.warnings.push(`${path}: ${reason}`);
    c.entries.push({ path, name, kind: "file", state: "blocked", size: 0, depth: path.split("/").length - 1 });
  }
}

async function walkHandle(c, handle, prefix, canTraverse = true) {
  const names = [];
  for await (const [name, entry] of handle.entries()) names.push([name, entry]);
  names.sort(([a], [b]) => a.localeCompare(b));

  for (const [name, entry] of names) {
    const path = prefix ? `${prefix}/${name}` : name;
    const depth = path.split("/").length - 1;
    if (entry.kind === "directory") {
      const ignored = c.ignoredFolders.matches(path);
      const marker = c.mode === "ia" ? await directoryHasMarker(entry) : false;
      const blocked = marker;
      const state = blocked ? "blocked" : ignored ? "ignored" : "folder";
      c.entries.push({ path, name, kind: "folder", state, depth });
      if (!ignored && !blocked) await walkHandle(c, entry, path);
      continue;
    }
    await ingestFile(c, path, name, () => entry.getFile());
  }
}

export async function readDirectoryHandle(handle, opts) {
  const c = createContext(opts);
  await walkHandle(c, handle, "");
  const files = c.files.sort((a, b) => a.path.localeCompare(b.path));
  c.entries.sort((a, b) => a.path.localeCompare(b.path));
  return {
    name: handle.name || "Projeto",
    files,
    entries: c.entries,
    warnings: c.warnings,
    errors: c.errors,
    sensitive: c.sensitive,
    sourceType: "directory-handle"
  };
}

export async function readFileList(fileList, opts) {
  const c = createContext(opts);
  let projectName = "Projeto";
  const files = [...fileList].sort((a, b) => {
    const ap = a.webkitRelativePath || a.name;
    const bp = b.webkitRelativePath || b.name;
    return ap.localeCompare(bp);
  });

  for (const file of files) {
    const rawPath = file.webkitRelativePath || file.name;
    const parts = rawPath.split("/").filter(Boolean);
    if (parts.length > 1) projectName = parts[0];
    const relative = parts.length > 1 ? parts.slice(1).join("/") : parts.join("/");

    // Mantém pastas visíveis na prévia, mas não percorre descendentes de uma pasta ignorada.
    const segments = relative.split("/");
    let ignoredAncestor = false;
    for (let i = 1; i < segments.length; i += 1) {
      const folderPath = segments.slice(0, i).join("/");
      if (c.ignoredFolders.matches(folderPath)) {
        ignoredAncestor = true;
        break;
      }
    }
    if (ignoredAncestor) continue;

    // O input webkitdirectory não fornece diretórios isolados. Eles são reconstruídos depois.
    await ingestFile(c, relative, file.name, async () => file);
  }

  const folderPaths = new Set();
  for (const entry of c.entries) {
    const parts = entry.path.split("/");
    for (let i = 1; i < parts.length; i += 1) folderPaths.add(parts.slice(0, i).join("/"));
  }
  for (const folderPath of folderPaths) {
    if (!c.entries.some((entry) => entry.kind === "folder" && entry.path === folderPath)) {
      const state = c.ignoredFolders.matches(folderPath) ? "ignored" : "folder";
      c.entries.push({
        path: folderPath,
        name: folderPath.split("/").pop(),
        kind: "folder",
        state,
        depth: folderPath.split("/").length - 1
      });
    }
  }

  // Mostra arquivos ignorados encontrados no input mesmo quando não foram lidos.
  for (const file of files) {
    const rawPath = file.webkitRelativePath || file.name;
    const parts = rawPath.split("/").filter(Boolean);
    const relative = parts.length > 1 ? parts.slice(1).join("/") : parts.join("/");
    const ancestorIgnored = c.entries.some((entry) =>
      entry.kind === "folder" && entry.state === "ignored" && (relative === entry.path || relative.startsWith(`${entry.path}/`))
    );
    if (ancestorIgnored) continue;
    if (!c.entries.some((entry) => entry.kind === "file" && entry.path === relative)) {
      let state = "blocked";
      if (isSensitiveName(file.name)) state = "blocked";
      else if (c.ignoredFiles.matches(relative)) state = "ignored";
      c.entries.push({
        path: relative,
        name: file.name,
        kind: "file",
        state,
        size: Number(file.size || 0),
        depth: relative.split("/").length - 1
      });
    }
  }

  c.entries.sort((a, b) => {
    const depthDiff = a.depth - b.depth;
    return depthDiff || a.path.localeCompare(b.path);
  });

  return {
    name: projectName,
    files: c.files.sort((a, b) => a.path.localeCompare(b.path)),
    entries: c.entries,
    warnings: c.warnings,
    errors: c.errors,
    sensitive: c.sensitive,
    sourceType: "file-list"
  };
}

export function renderTree(paths) {
  const root = {};
  for (const path of paths) {
    let node = root;
    for (const component of normalizeRelativePath(path).split("/")) node = node[component] ||= {};
  }
  const lines = [];
  function visit(node, prefix = "") {
    const entries = Object.entries(node).sort(([a], [b]) => a.localeCompare(b));
    entries.forEach(([name, children], index) => {
      const last = index === entries.length - 1;
      lines.push(`${prefix}${last ? "└── " : "├── "}${name}`);
      visit(children, prefix + (last ? "    " : "│   "));
    });
  }
  visit(root);
  return lines.join("\n");
}

const maxFenceLength = (text) => {
  const matches = String(text || "").match(/`+/g) || [];
  const longest = matches.reduce((max, item) => Math.max(max, item.length), 0);
  return "`".repeat(Math.max(3, longest + 1));
};

const tRender = {
  pt_BR: {
    project: (name) => `Projeto: ${name}`,
    treeTitle: "Árvore dos arquivos desta parte",
    file: (path, part) => `${path}${part ? ` — trecho ${part} (arquivo dividido)` : ""}`
  },
  en: {
    project: (name) => `Project: ${name}`,
    treeTitle: "File tree for this part",
    file: (path, part) => `${path}${part ? ` — fragment ${part} (split file)` : ""}`
  }
};

export function renderAI(name, blocks, { format = "Markdown", includeTree = true, language = "pt_BR" } = {}) {
  const md = format === "Markdown";
  const copy = tRender[language] || tRender.pt_BR;
  let output = `${md ? "# " : ""}${copy.project(name)}\n\n`;

  if (includeTree) {
    const tree = renderTree([...new Set(blocks.map((block) => block.path))].sort());
    output += `${md ? "## " : ""}${copy.treeTitle}\n\n`;
    if (md) {
      const fence = maxFenceLength(tree);
      output += `${fence}text\n${tree}\n${fence}\n\n`;
    } else {
      output += `${tree}\n\n`;
    }
  }

  for (const block of blocks) {
    const title = copy.file(block.path, block.part || 0);
    output += `${md ? "## " : "=== "}${title}\n\n`;
    if (md) {
      const fence = maxFenceLength(block.text);
      output += `${fence}${block.language || ""}\n${block.text}${block.text.endsWith("\n") ? "" : "\n"}${fence}\n\n`;
    } else {
      output += `${block.text}\n\n`;
    }
  }
  return output;
}

export function planAI(files, {
  format = "Markdown",
  tokenLimit = 30000,
  includeTree = true,
  split = true,
  name = "projeto",
  language = "pt_BR"
} = {}) {
  if (!Number.isInteger(tokenLimit) || tokenLimit < 100) {
    throw new Error("Informe um limite inteiro de pelo menos 100 tokens.");
  }
  if (!["Markdown", "TXT"].includes(format)) throw new Error("Escolha Markdown ou TXT.");

  const options = { format, includeTree, language };
  const selected = files
    .filter((file) => file.selected)
    .map((file) => ({ path: file.path, text: file.text, language: file.language, part: 0 }));

  const fits = (blocks) => estimateTokens(renderAI(name, blocks, options)) <= tokenLimit;
  const cannotFitMetadata = () => new Error("O limite não comporta os títulos e a árvore. Aumente o limite ou desative a árvore.");

  const groups = [];
  const divided = [];
  let current = [];

  for (const block of selected) {
    if (!split || fits([...current, block])) {
      current.push(block);
      continue;
    }

    if (current.length) {
      groups.push(current);
      current = [];
    }

    if (fits([block])) {
      current = [block];
      continue;
    }

    if (!block.text) throw cannotFitMetadata();
    divided.push(block.path);

    let rest = block.text;
    let partNumber = 1;

    while (rest) {
      let low = 0;
      let high = Math.min(rest.length, tokenLimit * 4);
      while (low < high) {
        const mid = Math.floor((low + high + 1) / 2);
        const candidate = { ...block, text: rest.slice(0, mid), part: partNumber };
        if (fits([candidate])) low = mid;
        else high = mid - 1;
      }
      if (!low) throw cannotFitMetadata();

      let cut = low;
      if (cut < rest.length) {
        const lineEnd = rest.lastIndexOf("\n", cut - 1);
        if (lineEnd >= 0) cut = lineEnd + 1;
      }

      const piece = { ...block, text: rest.slice(0, cut), part: partNumber };
      rest = rest.slice(cut);
      partNumber += 1;
      if (rest) groups.push([piece]);
      else current = [piece];
    }
  }

  if (current.length) groups.push(current);

  const extension = format === "Markdown" ? "md" : "txt";
  const base = safeName(name);
  const parts = groups.map((group, index) => {
    const text = renderAI(name, group, options);
    return {
      name: `${base}_parte_${String(index + 1).padStart(2, "0")}.${extension}`,
      text,
      tokens: estimateTokens(text)
    };
  });

  return {
    parts,
    divided,
    selected: selected.length,
    chars: selected.reduce((sum, block) => sum + block.text.length, 0),
    tokens: parts.reduce((sum, part) => sum + part.tokens, 0)
  };
}

export function buildSingle(files, name, language = "pt_BR") {
  const selected = files.filter((file) => file.selected);
  const prefix = language === "en" ? "PROJECT SUMMARY" : "RESUMO DO PROJETO";
  const fileLabel = language === "en" ? "FILE" : "ARQUIVO";
  const contentLabel = language === "en" ? "CONTENT" : "CONTEÚDO";
  return selected.reduce(
    (output, file) => `${output}${fileLabel}: ${file.path}\n${contentLabel}:\n${file.text}\n\n`,
    `${prefix}: ${name}\n\n`
  );
}

export function buildSeparate(files, language = "pt_BR") {
  const original = language === "en" ? "Original file" : "Arquivo original";
  const content = language === "en" ? "Content" : "Conteúdo";
  return files.filter((file) => file.selected).map((file) => ({
    name: `${file.path}.txt`,
    text: `${original}: ${file.path}\n\n${content}:\n\n${file.text}`
  }));
}

// ZIP no formato STORE (sem dependências externas).
const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(bytes) {
  let crc = -1;
  for (const byte of bytes) crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (~crc) >>> 0;
}

function writeU16(view, offset, value) { view.setUint16(offset, value, true); }
function writeU32(view, offset, value) { view.setUint32(offset, value, true); }

export function zip(entries) {
  const encoder = new TextEncoder();
  const chunks = [];
  const central = [];
  let offset = 0;

  for (const entry of entries) {
    const name = encoder.encode(entry.name.replace(/\\/g, "/"));
    const data = encoder.encode(entry.text);
    const crc = crc32(data);

    const local = new Uint8Array(30);
    const lv = new DataView(local.buffer);
    writeU32(lv, 0, 0x04034b50);
    writeU16(lv, 4, 20);
    writeU16(lv, 6, 0x0800);
    writeU32(lv, 14, crc);
    writeU32(lv, 18, data.length);
    writeU32(lv, 22, data.length);
    writeU16(lv, 26, name.length);

    const cd = new Uint8Array(46);
    const cv = new DataView(cd.buffer);
    writeU32(cv, 0, 0x02014b50);
    writeU16(cv, 4, 20);
    writeU16(cv, 6, 20);
    writeU16(cv, 8, 0x0800);
    writeU32(cv, 16, crc);
    writeU32(cv, 20, data.length);
    writeU32(cv, 24, data.length);
    writeU16(cv, 28, name.length);
    writeU32(cv, 42, offset);

    chunks.push(local, name, data);
    central.push(cd, name);
    offset += local.length + name.length + data.length;
  }

  const centralSize = central.reduce((total, part) => total + part.byteLength, 0);
  const end = new Uint8Array(22);
  const ev = new DataView(end.buffer);
  writeU32(ev, 0, 0x06054b50);
  writeU16(ev, 8, entries.length);
  writeU16(ev, 10, entries.length);
  writeU32(ev, 12, centralSize);
  writeU32(ev, 16, offset);

  return new Blob([...chunks, ...central, end], { type: "application/zip" });
}

export function applySelection(files, selectedPaths) {
  const selected = new Set([...selectedPaths].map(normalizeRelativePath));
  return files.map((file) => ({ ...file, selected: selected.has(file.path) }));
}

export function pathsOfSelected(files) {
  return new Set(files.filter((file) => file.selected).map((file) => file.path));
}

export function ruleMatches(rule, relativePath) {
  const value = String(rule ?? "").trim().replace(/\\/g, "/");
  const path = normalizeRelativePath(relativePath).toLowerCase();
  if (!value) return false;
  if (!value.includes("/") && !isWindowsAbsolute(value)) {
    return value.toLowerCase() === path.split("/").pop();
  }
  if (isWindowsAbsolute(value)) return false;
  return normalizeRelativePath(value).toLowerCase() === path;
}

export function removeMatchingRules(rules, relativePath) {
  return rules.filter((rule) => !ruleMatches(rule, relativePath));
}

export function makeProjectEntryStates(project, { ignoredFolders, ignoredFiles } = {}) {
  const folderFilter = new IgnoreFilter(ignoredFolders);
  const fileFilter = new IgnoreFilter(ignoredFiles);
  const selected = new Set(project.files.filter((file) => file.selected).map((file) => file.path));

  return project.entries.map((entry) => {
    if (entry.kind === "folder") {
      if (entry.state === "blocked") return { ...entry, state: "blocked" };
      if (folderFilter.matches(entry.path)) return { ...entry, state: "ignored" };
      return { ...entry, state: "folder" };
    }

    if (isSensitiveName(entry.name)) return { ...entry, state: "blocked" };
    if (fileFilter.matches(entry.path)) return { ...entry, state: "ignored" };
    const file = project.files.find((item) => item.path === entry.path);
    if (!file) return { ...entry, state: "blocked" };
    return { ...entry, state: selected.has(entry.path) ? "included" : "not-selected", size: file.size };
  });
}
