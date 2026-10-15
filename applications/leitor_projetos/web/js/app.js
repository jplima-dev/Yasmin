import {
  DEFAULTS,
  applySelection,
  buildSeparate,
  buildSingle,
  estimateTokens,
  makeProjectEntryStates,
  normalizeRelativePath,
  parseExtensions,
  parseLines,
  pathsOfSelected,
  planAI,
  readDirectoryHandle,
  readFileList,
  removeMatchingRules,
  ruleMatches,
  safeName,
  zip
} from "./project-reader.js";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const STORAGE_KEY = "project-reader:settings:v2";
const HISTORY_KEY = "project-reader:history:v2";

const state = {
  settings: null,
  project: null,
  source: null,
  activePath: null,
  query: "",
  previewActionSelection: new Set(),
  busy: false,
  language: "pt_BR",
  lastPlan: null
};

const I18N = {
  pt_BR: {
    title: "Leitor de Projetos", local: "● Processamento local", settings: "Configurações", help: "Ajuda", history: "Histórico",
    prepareProject: "PREPARAR PROJETO", heroTitle: "Transforme código em contexto organizado.",
    heroDescription: "Leia apenas o que importa, revise a seleção e exporte uma cópia pronta para documentação, compartilhamento ou IA.",
    project: "PROJETO", selectedProject: "Projeto selecionado", noFolder: "Nenhuma pasta selecionada.",
    selectFolder: "Selecionar pasta", previewFiles: "Pré-visualizar arquivos", reload: "Recarregar",
    folderHint: "Pastas ignoradas, arquivos sensíveis e itens fora dos filtros não são lidos.",
    processing: "PROCESSAMENTO", processingMode: "Modo de processamento",
    singleMode: "Arquivo único", singleDescription: "Cria um TXT consolidado com a estrutura e o conteúdo dos arquivos selecionados.",
    separateMode: "Arquivos separados", separateDescription: "Cria um TXT para cada arquivo, preservando a estrutura de pastas.",
    aiMode: "Preparar para IA", aiDescription: "Estima tokens e divide o contexto em partes Markdown ou TXT com limite configurável.",
    format: "Formato", tokenLimit: "Limite de tokens por parte", includeTree: "Incluir árvore dos arquivos",
    splitAutomatically: "Dividir automaticamente", output: "SAÍDA", destination: "Destino",
    browserDownload: "Download do navegador", browserDownloadDescription: "Por ser um módulo estático, os resultados são baixados pelo navegador. Sua pasta de Downloads continua sob controle do sistema.",
    selection: "SELEÇÃO", noProject: "Nenhum projeto carregado", export: "Gerar e exportar",
    selectVisible: "Selecionar visíveis", clearVisible: "Desmarcar visíveis", files: "Arquivos", manageSelection: "Gerenciar seleção",
    emptyTitle: "O projeto aparecerá aqui", emptyDescription: "Escolha uma pasta para listar os arquivos legíveis.",
    preview: "PRÉVIA", selectFile: "Selecione um arquivo", selected: "Selecionados", size: "Tamanho",
    estimatedTokens: "Tokens estimados", estimatedParts: "Partes estimadas", processingProject: "Processando projeto…",
    searchPlaceholder: "Filtrar por nome ou caminho",
    confirm: "CONFIRMAÇÃO", confirmProcessing: "Confirmar processamento", continueQuestion: "Deseja continuar?",
    continue: "Continuar", cancel: "Cancelar", complete: "CONCLUÍDO", transferComplete: "Transferência concluída",
    filesGenerated: "Os arquivos foram gerados e o download foi iniciado pelo navegador.", close: "Fechar",
    settingsTitle: "Configurações", extensionsTab: "Extensões", ignoredTab: "Pastas e arquivos ignorados", languageTab: "Idioma",
    singleExtensionsTitle: "Modo: Arquivo único / Preparar para IA", separateExtensionsTitle: "Modo: Arquivos separados",
    extensionsInfo: "Uma extensão por linha.", restoreDefault: "Restaurar padrão",
    ignoredFolders: "Pastas ignoradas", ignoredFoldersInfo: "Nomes simples valem em qualquer pasta; caminhos com / valem para o caminho indicado.",
    ignoredFiles: "Arquivos ignorados", protectedEnv: ".env é sempre protegido e não pode ser removido.",
    interfaceLanguage: "Idioma da interface", languageInfo: "A alteração é salva ao fechar as configurações.",
    settingsStored: "As preferências ficam apenas neste navegador e não incluem o conteúdo do projeto.",
    previewInstructions: "Use as caixas para incluir arquivos. Selecione linhas para aplicar ações em lote.",
    ignoreSelected: "Ignorar selecionados", includeSelected: "Incluir selecionados", selectAll: "Selecionar tudo",
    include: "Incluir", nameOrPath: "Nome ou caminho", type: "Tipo", status: "Estado", confirmSelection: "Confirmar seleção",
    clearHistory: "Limpar histórico", filesFound: "arquivos encontrados", included: "Incluído", ignored: "Ignorado",
    blocked: "Bloqueado", notSelected: "Não selecionado", folder: "Pasta", file: "Arquivo",
    warningSensitive: (n) => `Arquivos sensíveis ignorados: ${n}.`,
    warningErrors: (n) => `Arquivos com erro de leitura: ${n}.`,
    noReadableFiles: "Nenhum arquivo legível selecionado. Revise a seleção e os filtros.",
    tokenEstimateNote: "Estimativa: 1 token a cada 4 caracteres; varia conforme o modelo.",
    splitOffWarning: "Divisão automática desativada: a saída excede o limite informado.",
    dividedWarning: (paths) => `Arquivos divididos em trechos: ${paths.join(", ")}.`,
    savedSelection: (n) => `Seleção salva: ${n} arquivo(s).`,
    historyEmpty: "Nenhum processamento realizado ainda.",
    historyFiles: (n) => `${n} arquivo(s)`,
    modeSingle: "Arquivo único", modeSeparate: "Arquivos separados", modeAI: "Preparar para IA",
    found: "ENCONTRADOS", processed: "PROCESSADOS", ignoredCount: "IGNORADOS", errors: "ERROS",
    expectedCount: (n) => `Serão processados ${n} arquivos.`, sensitiveCount: (n) => `Arquivos sensíveis ignorados: ${n}.`,
    noSensitive: "Nenhum arquivo sensível encontrado.", modeHelpSingle: "Usa a lista de extensões do modo Arquivo único.",
    modeHelpSeparate: "Usa a lista de extensões específica do modo Arquivos separados.",
    modeHelpAI: "Usa as extensões de Arquivo único. Limite mínimo de 100 tokens.",
    chooseFolderFirst: "Selecione uma pasta de projeto primeiro.",
    processingBusy: "Já existe um processamento em andamento.",
    noBrowserFolder: "Seu navegador não oferece o seletor de pasta moderno; o seletor de diretório compatível foi aberto.",
    readDone: "Leitura concluída. Revise os arquivos antes de exportar.",
    selectionCanceled: "Seleção cancelada. Nenhum arquivo foi alterado.",
    exportStarted: "Download preparado.", restored: "Padrões restaurados.",
    settingsSaved: "Configurações salvas.", noSelection: "Nenhum arquivo selecionado.",
    invalidTokenLimit: "Informe um limite inteiro de pelo menos 100 tokens.",
    aiTooLarge: "A saída de IA excede o limite configurado e a divisão automática está desativada.",
    binaryWarning: "Arquivo não é texto legível (possível binário).",
    securityWarning: "Este arquivo é bloqueado por segurança.",
    errorPrefix: "Erro", unknownError: "Erro inesperado."
  },
  en: {
    title: "Project Reader", local: "● Local processing", settings: "Settings", help: "Help", history: "History",
    prepareProject: "PREPARE PROJECT", heroTitle: "Turn code into organized context.",
    heroDescription: "Read only what matters, review the selection, and export a copy ready for documentation, sharing, or AI.",
    project: "PROJECT", selectedProject: "Selected project", noFolder: "No folder selected.",
    selectFolder: "Select folder", previewFiles: "Preview files", reload: "Reload",
    folderHint: "Ignored folders, sensitive files, and items outside the filters are not read.",
    processing: "PROCESSING", processingMode: "Processing mode",
    singleMode: "Single file", singleDescription: "Creates one consolidated TXT with the structure and content of the selected files.",
    separateMode: "Separate files", separateDescription: "Creates one TXT per file, preserving the folder structure.",
    aiMode: "Prepare for AI", aiDescription: "Estimates tokens and splits context into Markdown or TXT parts with a configurable limit.",
    format: "Format", tokenLimit: "Token limit per part", includeTree: "Include file tree",
    splitAutomatically: "Split automatically", output: "OUTPUT", destination: "Destination",
    browserDownload: "Browser download", browserDownloadDescription: "Because this is a static module, results are downloaded by the browser. Your Downloads location remains under system control.",
    selection: "SELECTION", noProject: "No project loaded", export: "Generate and export",
    selectVisible: "Select visible", clearVisible: "Clear visible", files: "Files", manageSelection: "Manage selection",
    emptyTitle: "Your project will appear here", emptyDescription: "Choose a folder to list readable files.",
    preview: "PREVIEW", selectFile: "Select a file", selected: "Selected", size: "Size",
    estimatedTokens: "Estimated tokens", estimatedParts: "Estimated parts", processingProject: "Processing project…",
    searchPlaceholder: "Filter by name or path",
    confirm: "CONFIRM", confirmProcessing: "Confirm processing", continueQuestion: "Do you want to continue?",
    continue: "Continue", cancel: "Cancel", complete: "COMPLETE", transferComplete: "Transfer complete",
    filesGenerated: "Files were generated and the browser download was started.", close: "Close",
    settingsTitle: "Settings", extensionsTab: "Extensions", ignoredTab: "Ignored folders and files", languageTab: "Language",
    singleExtensionsTitle: "Mode: Single file / Prepare for AI", separateExtensionsTitle: "Mode: Separate files",
    extensionsInfo: "One extension per line.", restoreDefault: "Restore defaults",
    ignoredFolders: "Ignored folders", ignoredFoldersInfo: "Simple names apply in any folder; paths with / apply to the indicated path.",
    ignoredFiles: "Ignored files", protectedEnv: ".env is always protected and cannot be removed.",
    interfaceLanguage: "Interface language", languageInfo: "The change is saved when settings are closed.",
    settingsStored: "Preferences remain only in this browser and never include project content.",
    previewInstructions: "Use the checkboxes to include files. Select rows to apply bulk actions.",
    ignoreSelected: "Ignore selected", includeSelected: "Include selected", selectAll: "Select all",
    include: "Include", nameOrPath: "Name or path", type: "Type", status: "Status", confirmSelection: "Confirm selection",
    clearHistory: "Clear history", filesFound: "files found", included: "Included", ignored: "Ignored",
    blocked: "Blocked", notSelected: "Not selected", folder: "Folder", file: "File",
    warningSensitive: (n) => `Sensitive files skipped: ${n}.`,
    warningErrors: (n) => `Files with read errors: ${n}.`,
    noReadableFiles: "No readable files are selected. Review the selection and filters.",
    tokenEstimateNote: "Estimate: 1 token per 4 characters; varies by model.",
    splitOffWarning: "Automatic splitting is off: the output exceeds the requested limit.",
    dividedWarning: (paths) => `Files split into fragments: ${paths.join(", ")}.`,
    savedSelection: (n) => `Selection saved: ${n} file(s).`,
    historyEmpty: "No processing has been performed yet.",
    historyFiles: (n) => `${n} file(s)`,
    modeSingle: "Single file", modeSeparate: "Separate files", modeAI: "Prepare for AI",
    found: "FOUND", processed: "PROCESSED", ignoredCount: "IGNORED", errors: "ERRORS",
    expectedCount: (n) => `${n} files will be processed.`, sensitiveCount: (n) => `Sensitive files skipped: ${n}.`,
    noSensitive: "No sensitive files found.", modeHelpSingle: "Uses the Single file extension list.",
    modeHelpSeparate: "Uses the Separate files extension list.",
    modeHelpAI: "Uses the Single file extensions. Minimum limit is 100 tokens.",
    chooseFolderFirst: "Select a project folder first.", processingBusy: "A processing task is already running.",
    noBrowserFolder: "Your browser does not provide the modern folder picker; the compatible directory selector was opened.",
    readDone: "Reading completed. Review the files before exporting.",
    selectionCanceled: "Selection canceled. No files were changed.",
    exportStarted: "Download prepared.", restored: "Defaults restored.",
    settingsSaved: "Settings saved.", noSelection: "No files selected.",
    invalidTokenLimit: "Enter a whole number of at least 100 tokens.",
    aiTooLarge: "The AI output exceeds the configured limit and automatic splitting is disabled.",
    binaryWarning: "File is not readable text (possibly binary).",
    securityWarning: "This file is blocked for security reasons.",
    errorPrefix: "Error", unknownError: "Unexpected error."
  }
};

const t = (key, ...args) => {
  const value = I18N[state.language]?.[key] ?? I18N.pt_BR[key] ?? key;
  return typeof value === "function" ? value(...args) : value;
};

function loadJSON(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value === null ? fallback : JSON.parse(value);
  } catch {
    return fallback;
  }
}

function saveJSON(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); }
  catch { /* armazenamento indisponível não deve impedir o uso */ }
}

function cloneDefaults() {
  return {
    singleExtensions: [...DEFAULTS.singleExtensions],
    separateExtensions: [...DEFAULTS.separateExtensions],
    ignoredFolders: [...DEFAULTS.ignoredFolders],
    ignoredFiles: [...DEFAULTS.ignoredFiles],
    language: "pt_BR",
    format: "Markdown",
    tokenLimit: 30000,
    includeTree: true,
    split: true
  };
}

function loadSettings() {
  const raw = loadJSON(STORAGE_KEY, {});
  const defaults = cloneDefaults();
  const settings = { ...defaults, ...raw };
  for (const key of ["singleExtensions", "separateExtensions", "ignoredFolders", "ignoredFiles"]) {
    settings[key] = Array.isArray(settings[key]) ? settings[key].filter(Boolean).map(String) : [...defaults[key]];
  }
  settings.ignoredFiles = settings.ignoredFiles.includes(".env") ? settings.ignoredFiles : [".env", ...settings.ignoredFiles];
  settings.language = settings.language === "en" ? "en" : "pt_BR";
  settings.format = settings.format === "TXT" ? "TXT" : "Markdown";
  settings.tokenLimit = Number.isInteger(Number(settings.tokenLimit)) ? Number(settings.tokenLimit) : 30000;
  settings.includeTree = Boolean(settings.includeTree);
  settings.split = Boolean(settings.split);
  return settings;
}

function saveSettings() {
  state.settings.singleExtensions = parseExtensions($("#single-extensions").value);
  state.settings.separateExtensions = parseExtensions($("#separate-extensions").value);
  state.settings.ignoredFolders = parseLines($("#ignored-folders").value);
  state.settings.ignoredFiles = parseLines($("#ignored-files").value);
  if (!state.settings.ignoredFiles.some((value) => value.toLowerCase() === ".env")) {
    state.settings.ignoredFiles.unshift(".env");
  }
  state.settings.language = $$("input[name=language]").find((input) => input.checked)?.value || "pt_BR";
  state.settings.format = $("#format").value;
  state.settings.tokenLimit = Math.max(100, Number.parseInt($("#token-limit").value || "30000", 10));
  state.settings.includeTree = $("#include-tree").checked;
  state.settings.split = $("#split").checked;
  state.language = state.settings.language;
  saveJSON(STORAGE_KEY, state.settings);
}

function fillSettingsForm() {
  $("#single-extensions").value = state.settings.singleExtensions.join("\n");
  $("#separate-extensions").value = state.settings.separateExtensions.join("\n");
  $("#ignored-folders").value = state.settings.ignoredFolders.join("\n");
  $("#ignored-files").value = state.settings.ignoredFiles.join("\n");
  $("#format").value = state.settings.format;
  $("#token-limit").value = state.settings.tokenLimit;
  $("#include-tree").checked = state.settings.includeTree;
  $("#split").checked = state.settings.split;
  $$("input[name=language]").forEach((input) => { input.checked = input.value === state.language; });
}

function applyI18n() {
  document.documentElement.lang = state.language === "en" ? "en" : "pt-BR";
  $$("[data-i18n]").forEach((element) => {
    const key = element.dataset.i18n;
    element.textContent = t(key);
  });
  $$("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = t(element.dataset.i18nPlaceholder);
  });
  updateModeHelp();
  renderHelp();
  renderHistory();
}

function currentMode() {
  return $$("input[name=mode]").find((input) => input.checked)?.value || "single";
}

function extensionsForMode(mode = currentMode()) {
  return mode === "separate" ? state.settings.separateExtensions : state.settings.singleExtensions;
}

function getModeLabel(mode) {
  return mode === "ia" ? t("modeAI") : mode === "separate" ? t("modeSeparate") : t("modeSingle");
}

function updateModeHelp() {
  const mode = currentMode();
  $("#mode-help").textContent = mode === "ia"
    ? `${t("modeHelpAI")} ${t("tokenEstimateNote")}`
    : mode === "separate" ? t("modeHelpSeparate") : t("modeHelpSingle");
  const aiControls = [$("#format").closest("label"), $("#token-limit").closest("label"), $("#include-tree").closest("label"), $("#split").closest("label")];
  aiControls.forEach((element) => { if (element) element.style.opacity = mode === "ia" ? "1" : ".55"; });
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(1)} GB`;
}

function visibleFiles() {
  if (!state.project) return [];
  const query = state.query.trim().toLowerCase();
  return query ? state.project.files.filter((file) => file.path.toLowerCase().includes(query)) : state.project.files;
}

function selectedFiles() {
  return state.project?.files.filter((file) => file.selected) || [];
}

function setBusy(busy) {
  state.busy = busy;
  $("#choose-folder").disabled = busy;
  $("#export").disabled = busy || !selectedFiles().length;
  $("#open-preview").disabled = busy || !state.project;
  $("#open-preview-inline").disabled = busy || !state.project;
  $("#reload-project").disabled = busy || !state.source;
  $("#select-visible").disabled = busy || !state.project;
  $("#clear-visible").disabled = busy || !state.project;
  $$("input[name=mode]").forEach((input) => input.disabled = busy);
}

function toast(message, danger = false) {
  const existing = $(".pr-toast");
  existing?.remove();
  const element = document.createElement("div");
  element.className = `pr-toast${danger ? " danger" : ""}`;
  element.textContent = message;
  document.body.append(element);
  setTimeout(() => element.remove(), 2800);
  if (!danger) globalThis.Mega?.ui?.toast?.(message, { tone: "success" });
}

function showModal(id) {
  const layer = document.getElementById(id);
  if (!layer) return;
  layer.hidden = false;
  const dialog = layer.querySelector('[role="dialog"]');
  const focusable = dialog?.querySelector("button, input, select, textarea");
  focusable?.focus();
}

function closeModal(id) {
  const layer = document.getElementById(id);
  if (layer) layer.hidden = true;
}

function closeAllModals() {
  $$(".pr-modal-layer").forEach((layer) => { layer.hidden = true; });
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob instanceof Blob ? blob : new Blob([blob]));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1200);
}

function downloadText(text, filename, mime = "text/plain;charset=utf-8") {
  downloadBlob(new Blob([text], { type: mime }), filename);
}

function projectPathLabel() {
  return state.project?.name || t("noFolder");
}

function renderMainList() {
  const list = $("#file-list");
  list.replaceChildren();

  const files = visibleFiles();
  $("#file-count").textContent = String(state.project?.files.length || 0);
  $("#empty").hidden = Boolean(files.length);

  for (const file of files) {
    const row = document.createElement("label");
    row.className = `pr-file-row${file.path === state.activePath ? " is-active" : ""}`;
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = file.selected;
    checkbox.setAttribute("aria-label", file.path);
    checkbox.addEventListener("click", (event) => event.stopPropagation());
    checkbox.addEventListener("change", () => {
      file.selected = checkbox.checked;
      updateSelectionMetrics();
    });

    const copy = document.createElement("span");
    copy.className = "pr-file-copy";
    const strong = document.createElement("strong");
    strong.textContent = file.name;
    const small = document.createElement("small");
    small.textContent = file.path;
    copy.append(strong, small);

    const meta = document.createElement("span");
    meta.className = "pr-file-meta";
    meta.textContent = formatBytes(file.size);

    row.append(checkbox, copy, meta);
    row.addEventListener("click", () => showActiveFile(file.path));
    list.append(row);
  }

  if (!files.length && state.project) {
    $("#empty").hidden = false;
    const message = $("#emptyDescription");
  }
}

function showActiveFile(path) {
  state.activePath = path;
  const file = state.project?.files.find((item) => item.path === path);
  if (!file) return;
  $("#preview-name").textContent = file.path;
  $("#preview").textContent = file.text || "Arquivo vazio.";
  renderMainList();
}

function updateSelectionMetrics() {
  const selected = selectedFiles();
  const chars = selected.reduce((sum, file) => sum + file.text.length, 0);
  const bytes = selected.reduce((sum, file) => sum + file.size, 0);

  $("#selected-count").textContent = String(selected.length);
  $("#selected-size").textContent = formatBytes(bytes);
  $("#token-estimate").textContent = estimateTokens(selected.map((file) => file.text).join("\n")).toLocaleString(state.language === "en" ? "en-US" : "pt-BR");
  $("#summary").textContent = state.project
    ? `${selected.length} / ${state.project.files.length} ${t("filesFound")} · ${formatBytes(bytes)}`
    : t("chooseFolderFirst");

  if (!state.project || !selected.length) {
    $("#part-estimate").textContent = "—";
    state.lastPlan = null;
    $("#warnings").hidden = true;
    setBusy(state.busy);
    return;
  }

  const mode = currentMode();
  const warnings = [];
  if (state.project.sensitive) warnings.push(t("warningSensitive", state.project.sensitive));
  if (state.project.errors.length) warnings.push(t("warningErrors", state.project.errors.length));

  if (mode === "ia") {
    try {
      const plan = planAI(state.project.files, {
        format: $("#format").value,
        tokenLimit: parseTokenLimit(),
        includeTree: $("#include-tree").checked,
        split: $("#split").checked,
        name: state.project.name,
        language: state.language
      });
      state.lastPlan = plan;
      $("#part-estimate").textContent = String(plan.parts.length);
      $("#token-estimate").textContent = plan.tokens.toLocaleString(state.language === "en" ? "en-US" : "pt-BR");
      if (plan.divided.length) warnings.push(t("dividedWarning", plan.divided));
      if (!$("#split").checked && plan.parts.some((part) => part.tokens > parseTokenLimit())) warnings.push(t("splitOffWarning"));
    } catch (error) {
      state.lastPlan = null;
      $("#part-estimate").textContent = "—";
      warnings.push(error?.message || t("unknownError"));
    }
  } else {
    state.lastPlan = null;
    $("#part-estimate").textContent = mode === "single" ? "1" : selected.length ? String(1) : "—";
  }

  const warningBox = $("#warnings");
  warningBox.hidden = warnings.length === 0;
  warningBox.textContent = warnings.join(" ");

  const exportBlocked = !selected.length || (mode === "ia" && state.lastPlan === null);
  $("#export").disabled = state.busy || exportBlocked;
}

function parseTokenLimit() {
  const value = Number.parseInt(String($("#token-limit").value).replace(/[.,\s]/g, ""), 10);
  if (!Number.isInteger(value) || value < 100) throw new Error(t("invalidTokenLimit"));
  return value;
}

function updateFolderLabels() {
  $("#project-path").textContent = projectPathLabel();
  $("#project-name").textContent = state.project?.name || t("noProject");
  $("#folder-help").textContent = state.project ? t("readDone") : t("folderHint");
}

function resetProjectUi() {
  $("#search").disabled = true;
  $("#search").value = "";
  state.query = "";
  $("#select-visible").disabled = true;
  $("#clear-visible").disabled = true;
  $("#open-preview").disabled = true;
  $("#open-preview-inline").disabled = true;
  $("#reload-project").disabled = !state.source;
  $("#file-list").replaceChildren();
  $("#empty").hidden = false;
  $("#file-count").textContent = "0";
  $("#preview-name").textContent = t("selectFile");
  $("#preview").textContent = "A prévia do conteúdo será exibida aqui.";
  $("#selected-count").textContent = "0";
  $("#selected-size").textContent = "0 B";
  $("#token-estimate").textContent = "0";
  $("#part-estimate").textContent = "—";
}

async function reloadProject({ preserveSelection = true } = {}) {
  if (!state.source) throw new Error(t("chooseFolderFirst"));
  const selectedPaths = preserveSelection && state.project ? pathsOfSelected(state.project.files) : null;
  const mode = currentMode();
  const opts = {
    extensions: extensionsForMode(mode),
    ignoredFolders: state.settings.ignoredFolders,
    ignoredFiles: state.settings.ignoredFiles,
    selectedPaths,
    mode
  };

  setBusy(true);
  $("#folder-help").textContent = t("processingProject");
  $("#progress-card").hidden = false;
  $("#progress-status").textContent = t("processingProject");
  $("#progress-file").textContent = "";
  $("#progress-counter").textContent = "0 / 0";
  $("#progress-bar").style.width = "0%";

  try {
    if (state.source.type === "directory") {
      state.project = await readDirectoryHandle(state.source.handle, {
        ...opts,
        onProgress: ({ path, current, total }) => {
          $("#progress-file").textContent = path;
          $("#progress-counter").textContent = `${current} / ${total}`;
          $("#progress-bar").style.width = total ? `${(current / total) * 100}%` : "0%";
        }
      });
    } else {
      state.project = await readFileList(state.source.files, opts);
    }

    state.activePath = state.project.files[0]?.path || null;
    $("#search").disabled = false;
    updateFolderLabels();
    renderMainList();
    if (state.activePath) showActiveFile(state.activePath);
    $("#progress-card").hidden = true;
    updateSelectionMetrics();
  } finally {
    setBusy(false);
    $("#progress-card").hidden = true;
    updateSelectionMetrics();
  }
}

async function chooseFolder() {
  if (state.busy) return;
  setBusy(true);
  try {
    if ("showDirectoryPicker" in window) {
      const handle = await window.showDirectoryPicker({ mode: "read", id: "project-reader" });
      state.source = { type: "directory", handle };
      state.project = null;
      state.activePath = null;
      state.settings.format = $("#format").value;
      state.settings.tokenLimit = parseTokenLimit();
      state.settings.includeTree = $("#include-tree").checked;
      state.settings.split = $("#split").checked;
      state.settings.singleExtensions = parseExtensions($("#single-extensions").value);
      state.settings.separateExtensions = parseExtensions($("#separate-extensions").value);
      state.settings.ignoredFolders = parseLines($("#ignored-folders").value);
      state.settings.ignoredFiles = parseLines($("#ignored-files").value);
      await reloadProject({ preserveSelection: false });
    } else {
      toast(t("noBrowserFolder"));
      $("#folder-input").click();
      setBusy(false);
    }
  } catch (error) {
    setBusy(false);
    if (error?.name !== "AbortError") toast(error?.message || t("unknownError"), true);
    $("#folder-help").textContent = t("selectionCanceled");
  }
}

async function handleFileInput(event) {
  const files = [...event.target.files || []];
  event.target.value = "";
  if (!files.length) return;
  state.source = { type: "files", files };
  state.project = null;
  state.activePath = null;
  setBusy(true);
  try {
    await reloadProject({ preserveSelection: false });
  } catch (error) {
    toast(error?.message || t("unknownError"), true);
  } finally {
    setBusy(false);
  }
}

function updateSettingsModalFromState() {
  fillSettingsForm();
  $$(".pr-tab").forEach((button) => button.classList.toggle("is-active", button.dataset.settingsTab === "extensions"));
  $$(".pr-settings-pane").forEach((pane) => { pane.hidden = pane.dataset.settingsPane !== "extensions"; });
}

function openSettings() {
  state.settings = {
    ...state.settings
  };
  updateSettingsModalFromState();
  showModal("settings-modal");
}

async function closeSettingsAndSave() {
  saveSettings();
  closeModal("settings-modal");
  applyI18n();
  if (state.source) {
    const previousPaths = pathsOfSelected(state.project?.files || []);
    state.project = null;
    try {
      await reloadProject({ preserveSelection: false });
      if (previousPaths.size) {
        const allowed = new Set(state.project.files.map((file) => file.path));
        const selected = new Set([...previousPaths].filter((path) => allowed.has(path)));
        state.project.files.forEach((file) => { file.selected = selected.has(file.path); });
        updateSelectionMetrics();
        renderMainList();
      }
    } catch (error) {
      toast(error?.message || t("unknownError"), true);
    }
  } else {
    updateFolderLabels();
    updateSelectionMetrics();
  }
  toast(t("settingsSaved"));
}

function switchSettingsTab(tab) {
  $$(".pr-tab").forEach((button) => button.classList.toggle("is-active", button.dataset.settingsTab === tab));
  $$(".pr-settings-pane").forEach((pane) => { pane.hidden = pane.dataset.settingsPane !== tab; });
}

function restoreSettingDefaults(which) {
  if (which === "single") $("#single-extensions").value = DEFAULTS.singleExtensions.join("\n");
  if (which === "separate") $("#separate-extensions").value = DEFAULTS.separateExtensions.join("\n");
  if (which === "folders") $("#ignored-folders").value = DEFAULTS.ignoredFolders.join("\n");
  if (which === "files") $("#ignored-files").value = DEFAULTS.ignoredFiles.join("\n");
  toast(t("restored"));
}

function buildPreviewSelection() {
  state.previewActionSelection.clear();
  renderPreviewTable();
}

function previewState() {
  if (!state.project) return [];
  return makeProjectEntryStates(state.project, {
    ignoredFolders: state.settings.ignoredFolders,
    ignoredFiles: state.settings.ignoredFiles
  }).sort((a, b) => {
    const depthDiff = a.depth - b.depth;
    return depthDiff || a.path.localeCompare(b.path);
  });
}

function renderPreviewTable() {
  const tbody = $("#preview-tree");
  tbody.replaceChildren();
  const entries = previewState();

  for (const entry of entries) {
    const row = document.createElement("tr");
    row.className = state.previewActionSelection.has(entry.path) ? "is-action-selected" : "";

    const includeCell = document.createElement("td");
    const includeCheckbox = document.createElement("input");
    includeCheckbox.type = "checkbox";
    includeCheckbox.disabled = entry.state === "blocked" || entry.kind === "folder";
    const file = state.project?.files.find((item) => item.path === entry.path);
    includeCheckbox.checked = Boolean(file?.selected);
    includeCheckbox.addEventListener("click", (event) => event.stopPropagation());
    includeCheckbox.addEventListener("change", () => {
      if (file) {
        file.selected = includeCheckbox.checked;
        updateSelectionMetrics();
        renderPreviewTable();
      }
    });
    includeCell.append(includeCheckbox);

    const pathCell = document.createElement("td");
    pathCell.className = "pr-tree-cell";
    pathCell.style.setProperty("--depth", String(entry.depth));
    const indent = document.createElement("span");
    indent.className = "pr-tree-indent";
    const icon = document.createElement("span");
    icon.className = "pr-tree-icon";
    icon.textContent = entry.kind === "folder" ? "▸" : "•";
    const pathCopy = document.createElement("span");
    pathCopy.className = "pr-tree-path";
    const strong = document.createElement("strong");
    strong.textContent = entry.name;
    const small = document.createElement("small");
    small.textContent = entry.path;
    pathCopy.append(strong, small);
    pathCell.append(indent, icon, pathCopy);

    const typeCell = document.createElement("td");
    typeCell.textContent = entry.kind === "folder" ? t("folder") : t("file");

    const stateCell = document.createElement("td");
    const stateSpan = document.createElement("span");
    stateSpan.className = `pr-state ${entry.state.replace("_", "-")}`;
    stateSpan.textContent = entry.state === "included" || entry.state === "folder" ? t("included")
      : entry.state === "ignored" ? t("ignored")
      : entry.state === "blocked" ? t("blocked") : t("notSelected");
    stateCell.append(stateSpan);

    const sizeCell = document.createElement("td");
    sizeCell.textContent = entry.kind === "file" ? formatBytes(entry.size) : "—";

    row.append(includeCell, pathCell, typeCell, stateCell, sizeCell);
    row.addEventListener("click", () => {
      if (state.previewActionSelection.has(entry.path)) state.previewActionSelection.delete(entry.path);
      else state.previewActionSelection.add(entry.path);
      renderPreviewTable();
      updatePreviewButtons();
    });
    tbody.append(row);
  }

  const includedCount = state.project?.files.filter((file) => file.selected).length || 0;
  const ignoredCount = entries.filter((entry) => entry.kind === "file" && ["ignored", "blocked", "not-selected"].includes(entry.state)).length;
  $("#preview-summary").textContent = `${t("savedSelection", includedCount)} ${t("filesFound")}: ${state.project?.files.length || 0}. ${t("ignored")}: ${ignoredCount}.`;
  updatePreviewButtons();
}

function updatePreviewButtons() {
  const selectedRows = [...state.previewActionSelection];
  const enabled = selectedRows.length > 0 && state.project;
  const selectableRows = selectedRows.some((path) => {
    const entry = previewState().find((item) => item.path === path);
    return entry && entry.state !== "blocked";
  });
  $("#preview-ignore").disabled = !enabled || !selectableRows;
  $("#preview-include").disabled = !enabled || !selectableRows;
}

function applyPreviewRule(action) {
  const selected = [...state.previewActionSelection];
  if (!selected.length) return;

  const entries = previewState().filter((entry) => selected.includes(entry.path) && entry.state !== "blocked");

  const selectedFolders = entries.filter((entry) => entry.kind === "folder").map((entry) => entry.path);
  const parentFolderChosen = (path) => selectedFolders.some((folder) => path === folder || path.startsWith(`${folder}/`));

  if (action === "ignore") {
    for (const entry of entries) {
      if (entry.kind === "folder") {
        if (!state.settings.ignoredFolders.includes(`./${entry.path}`)) state.settings.ignoredFolders.push(`./${entry.path}`);
      } else if (!parentFolderChosen(entry.path)) {
        if (!state.settings.ignoredFiles.includes(`./${entry.path}`)) state.settings.ignoredFiles.push(`./${entry.path}`);
      }
    }
  } else {
    for (const entry of entries) {
      if (entry.kind === "folder") state.settings.ignoredFolders = removeMatchingRules(state.settings.ignoredFolders, entry.path);
      else state.settings.ignoredFiles = removeMatchingRules(state.settings.ignoredFiles, entry.path);
    }

    for (const file of state.project.files) {
      if (entries.some((entry) => entry.kind === "folder" && (file.path === entry.path || file.path.startsWith(`${entry.path}/`))) || entries.some((entry) => entry.kind === "file" && entry.path === file.path)) {
        file.selected = true;
      }
    }
  }

  saveJSON(STORAGE_KEY, state.settings);
  state.previewActionSelection.clear();
  reloadProject({ preserveSelection: true }).then(() => renderPreviewTable()).catch((error) => toast(error?.message || t("unknownError"), true));
}

function openPreview() {
  if (!state.project) {
    toast(t("chooseFolderFirst"), true);
    return;
  }
  state.previewActionSelection.clear();
  renderPreviewTable();
  showModal("preview-modal");
}

function confirmPreview() {
  const selected = pathsOfSelected(state.project?.files || []);
  state.settings.ignoredFolders = parseLines(state.settings.ignoredFolders.join("\n"));
  state.settings.ignoredFiles = parseLines(state.settings.ignoredFiles.join("\n"));
  saveJSON(STORAGE_KEY, state.settings);
  closeModal("preview-modal");
  toast(t("savedSelection", selected.size));
  updateSelectionMetrics();
}

function openHistory() {
  renderHistory();
  showModal("history-modal");
}

function historyEntries() {
  return loadJSON(HISTORY_KEY, []);
}

function addHistory(entry) {
  const items = historyEntries();
  items.unshift(entry);
  saveJSON(HISTORY_KEY, items.slice(0, 50));
}

function renderHistory() {
  const container = $("#history-list");
  if (!container) return;
  const items = historyEntries();
  container.replaceChildren();

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "pr-empty";
    empty.style.minHeight = "180px";
    const strong = document.createElement("strong");
    strong.textContent = t("historyEmpty");
    empty.append(strong);
    container.append(empty);
    $("#clear-history").disabled = true;
    return;
  }

  $("#clear-history").disabled = false;
  for (const item of items) {
    const row = document.createElement("div");
    row.className = "pr-history-item";
    const title = document.createElement("strong");
    title.textContent = `${item.date} — ${item.project}`;
    const detail = document.createElement("span");
    detail.textContent = `${item.files} ${t("filesFound")} · ${item.mode}`;
    row.append(title, detail);
    container.append(row);
  }
}

function clearHistory() {
  localStorage.removeItem(HISTORY_KEY);
  renderHistory();
  toast(t("clearHistory"));
}

function renderHelp() {
  const container = $("#help-content");
  if (!container) return;
  container.innerHTML = "";

  const sections = state.language === "en" ? [
    ["What it does", "Converts code projects into text for analysis, documentation, sharing, and AI use."],
    ["Processing modes", "Single file creates one consolidated TXT. Separate files creates one TXT per source file. Prepare for AI estimates tokens and splits the project into Markdown or TXT parts using the Single file filters."],
    ["Selecting a project", "Choose the root folder of your code. Modern browsers can read the selected folder without uploading it to a server."],
    ["Filters", "Settings keep independent extension lists for Single file/AI and Separate files. Ignored folder and file rules can be names or project-relative paths."],
    ["Security", ".env, common credential names, and filenames containing terms such as secret, password, token, apikey, or credential are blocked by name before reading."],
    ["Output", "Static-web exports download through the browser. The module does not need a server-side Python process."]
  ] : [
    ["Para que serve", "Transforma projetos de código em texto para análise, documentação, compartilhamento e uso com IAs."],
    ["Modos de processamento", "Arquivo único cria um TXT consolidado. Arquivos separados cria um TXT por arquivo. Preparar para IA estima tokens e divide o projeto em partes Markdown ou TXT usando os filtros de Arquivo único."],
    ["Como selecionar um projeto", "Escolha a pasta raiz do código. O navegador lê apenas os arquivos compatíveis com os filtros."],
    ["Filtros", "As configurações mantêm listas de extensões independentes para Arquivo único/IA e Arquivos separados. Pastas e arquivos ignorados podem ser nomes ou caminhos relativos ao projeto."],
    ["Segurança", ".env e nomes comuns de credenciais, além de arquivos cujo nome contém termos como secret, password, token, apikey ou credential, são bloqueados antes da leitura."],
    ["Saída", "Como este é um módulo static-web, os resultados são baixados pelo navegador e não exigem um processo Python no computador."]
  ];

  const version = document.createElement("p");
  version.textContent = "Leitor de Projetos 1.1.0";
  container.append(version);

  for (const [heading, text] of sections) {
    const h = document.createElement("h3");
    h.textContent = heading;
    const p = document.createElement("p");
    p.textContent = text;
    container.append(h, p);
  }
}

function openConfirm() {
  const selected = selectedFiles();
  if (!selected.length) {
    toast(t("noSelection"), true);
    return;
  }
  $("#confirm-count").textContent = t("expectedCount", selected.length);
  $("#confirm-sensitive").textContent = state.project.sensitive ? t("sensitiveCount", state.project.sensitive) : t("noSensitive");
  showModal("confirm-modal");
}

async function exportProject() {
  if (state.busy || !state.project) return;
  const selected = selectedFiles();
  if (!selected.length) {
    toast(t("noSelection"), true);
    return;
  }

  state.busy = true;
  setBusy(true);
  $("#progress-card").hidden = false;
  $("#progress-status").textContent = t("processingProject");
  $("#progress-file").textContent = "";
  $("#progress-counter").textContent = "1 / 1";
  $("#progress-bar").style.width = "25%";

  try {
    const mode = currentMode();
    const base = safeName(state.project.name);
    let blob;
    let filename;
    let generatedCount = 0;

    if (mode === "ia") {
      const plan = planAI(state.project.files, {
        format: $("#format").value,
        tokenLimit: parseTokenLimit(),
        includeTree: $("#include-tree").checked,
        split: $("#split").checked,
        name: state.project.name,
        language: state.language
      });
      if (!plan.parts.length) throw new Error(t("noReadableFiles"));
      state.lastPlan = plan;
      generatedCount = plan.parts.length;
      if (plan.parts.length === 1) {
        blob = new Blob([plan.parts[0].text], { type: $("#format").value === "Markdown" ? "text/markdown;charset=utf-8" : "text/plain;charset=utf-8" });
        filename = plan.parts[0].name;
      } else {
        blob = zip(plan.parts);
        filename = `${base}_IA.zip`;
      }
    } else if (mode === "single") {
      const text = buildSingle(state.project.files, state.project.name, state.language);
      blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      filename = `${base}.txt`;
      generatedCount = 1;
    } else {
      const entries = buildSeparate(state.project.files, state.language);
      if (!entries.length) throw new Error(t("noReadableFiles"));
      blob = zip(entries);
      filename = `${base}_separado.zip`;
      generatedCount = entries.length;
    }

    $("#progress-bar").style.width = "100%";
    downloadBlob(blob, filename);

    addHistory({
      date: new Date().toLocaleString(state.language === "en" ? "en-US" : "pt-BR"),
      project: state.project.name,
      files: selected.length,
      mode: getModeLabel(mode),
      output: filename
    });

    showResult({
      found: state.project.entries.filter((entry) => entry.kind === "file").length,
      processed: selected.length,
      ignored: Math.max(0, state.project.entries.filter((entry) => entry.kind === "file").length - selected.length),
      errors: state.project.errors.length,
      generated: generatedCount,
      output: filename
    });
    renderHistory();
  } catch (error) {
    toast(`${t("errorPrefix")}: ${error?.message || t("unknownError")}`, true);
  } finally {
    state.busy = false;
    $("#progress-card").hidden = true;
    setBusy(false);
    updateSelectionMetrics();
  }
}

function showResult(summary) {
  const metrics = [
    [summary.found, t("found")],
    [summary.processed, t("processed")],
    [summary.ignored, t("ignoredCount")],
    [summary.errors, t("errors")]
  ];
  const container = $("#result-metrics");
  container.replaceChildren();
  for (const [value, label] of metrics) {
    const item = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = String(value);
    const span = document.createElement("span");
    span.textContent = label;
    item.append(strong, span);
    container.append(item);
  }

  const errors = $("#result-errors");
  if (state.project?.errors.length) {
    errors.hidden = false;
    errors.textContent = `${t("errorPrefix")}: ${state.project.errors.join("\n")}`;
  } else {
    errors.hidden = true;
    errors.textContent = "";
  }
  const note = document.createElement("div");
  note.className = "pr-result-head";
  note.style.paddingTop = "0";
  const p = document.createElement("p");
  p.textContent = `${t("exportStarted")} · ${summary.output}`;
  note.append(p);
  container.after(note);
  showModal("result-modal");
}

function onModeChange() {
  if (state.busy) return;
  updateModeHelp();
  state.project = state.project ? { ...state.project } : state.project;
  if (state.source) {
    state.project = null;
    reloadProject({ preserveSelection: false }).catch((error) => toast(error?.message || t("unknownError"), true));
  } else {
    updateSelectionMetrics();
  }
}

function persistInlineSettings() {
  state.settings.format = $("#format").value;
  state.settings.tokenLimit = Number.parseInt($("#token-limit").value || "30000", 10);
  state.settings.includeTree = $("#include-tree").checked;
  state.settings.split = $("#split").checked;
  saveJSON(STORAGE_KEY, state.settings);
  updateSelectionMetrics();
}

function wireEvents() {
  $("#choose-folder").addEventListener("click", chooseFolder);
  $("#folder-input").addEventListener("change", handleFileInput);
  $("#open-preview").addEventListener("click", openPreview);
  $("#open-preview-inline").addEventListener("click", openPreview);
  $("#reload-project").addEventListener("click", () => reloadProject({ preserveSelection: true }).catch((error) => toast(error?.message || t("unknownError"), true)));

  $("#search").addEventListener("input", (event) => { state.query = event.target.value; renderMainList(); });
  $("#select-visible").addEventListener("click", () => {
    visibleFiles().forEach((file) => { file.selected = true; });
    updateSelectionMetrics(); renderMainList();
  });
  $("#clear-visible").addEventListener("click", () => {
    visibleFiles().forEach((file) => { file.selected = false; });
    updateSelectionMetrics(); renderMainList();
  });

  $$("input[name=mode]").forEach((input) => input.addEventListener("change", onModeChange));
  ["#format", "#token-limit", "#include-tree", "#split"].forEach((selector) => {
    $(selector).addEventListener("change", persistInlineSettings);
    $(selector).addEventListener("input", persistInlineSettings);
  });

  $("#export").addEventListener("click", openConfirm);
  $("#confirm-go").addEventListener("click", () => { closeModal("confirm-modal"); exportProject(); });

  $("#open-settings").addEventListener("click", openSettings);
  $("#save-settings").addEventListener("click", closeSettingsAndSave);
  $("#open-help").addEventListener("click", () => { renderHelp(); showModal("help-modal"); });
  $("#open-history").addEventListener("click", openHistory);
  $("#clear-history").addEventListener("click", clearHistory);

  $$("[data-settings-tab]").forEach((button) => button.addEventListener("click", () => switchSettingsTab(button.dataset.settingsTab)));
  $("#restore-single-extensions").addEventListener("click", () => restoreSettingDefaults("single"));
  $("#restore-separate-extensions").addEventListener("click", () => restoreSettingDefaults("separate"));
  $("#restore-folders").addEventListener("click", () => restoreSettingDefaults("folders"));
  $("#restore-files").addEventListener("click", () => restoreSettingDefaults("files"));

  $("#preview-ignore").addEventListener("click", () => applyPreviewRule("ignore"));
  $("#preview-include").addEventListener("click", () => applyPreviewRule("include"));
  $("#preview-select-all").addEventListener("click", () => {
    state.previewActionSelection = new Set(previewState().filter((entry) => entry.state !== "blocked").map((entry) => entry.path));
    renderPreviewTable();
  });
  $("#preview-confirm").addEventListener("click", confirmPreview);

  $$("[data-close]").forEach((button) => button.addEventListener("click", () => closeModal(button.dataset.close)));
  $$(".pr-modal-layer").forEach((layer) => {
    layer.addEventListener("click", (event) => {
      if (event.target === layer && layer.id !== "confirm-modal") closeModal(layer.id);
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      const open = $$(".pr-modal-layer").find((layer) => !layer.hidden);
      if (open && open.id !== "confirm-modal") closeModal(open.id);
    }
  });
}

function boot() {
  state.settings = loadSettings();
  state.language = state.settings.language;
  fillSettingsForm();
  applyI18n();
  wireEvents();
  resetProjectUi();
  updateModeHelp();
  updateSelectionMetrics();
}

boot();
