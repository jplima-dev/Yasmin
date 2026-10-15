import { Settings } from "../settings.js";
import { BlackBox } from "../blackbox.js";
import { apiRequest, coreUrl } from "../origin.js";
import { subdivideView, unSubdivideView } from "../split-view.js";

const HISTORY_KEY = "workspace.terminal.history";
const HISTORY_ENABLED_KEY = "workspace.terminal.history.enabled";
const HISTORY_LIMIT = 50;
const SENSITIVE_COMMAND = /(?:password|passwd|token|secret|api[_-]?key|authorization)(?:\s|=|:)+\S+/i;
const STYLE_URL = coreUrl("/core/components/terminal.css");
const COMMANDS = [
  ["help", "lista todos os comandos"], ["clear", "limpa a tela"], ["modules", "lista os módulos"],
  ["subdivide", "divide a tela em duas instâncias"], ["unsubidivide", "volta para uma tela escolhida"],
  ["status", "resume a saúde do ecossistema"], ["diagnostics", "mostra navegador, armazenamento e módulos"],
  ["settings", "mostra as preferências globais"], ["recent", "lista arquivos da Drop Zone"],
  ["favorites", "lista favoritos"], ["favorite ", "adiciona um módulo aos favoritos"],
  ["unfavorite ", "remove um módulo dos favoritos"], ["open ", "abre módulo ou seção"],
  ["find ", "procura módulos"], ["ping ", "verifica um módulo"], ["start ", "inicia um serviço"],
  ["stop ", "para um serviço"], ["config bridge", "abre a configuração do Bridge"],
  ["config ink-driver", "abre a configuração do InkDriver"], ["theme ", "altera o tema global"],
  ["accent #", "altera a cor principal"], ["density ", "altera a densidade"],
  ["font ", "altera o tamanho do texto"], ["drop", "abre a Drop Zone"],
  ["clipboard", "abre o clipboard interno"], ["clip add ", "adiciona texto ao clipboard interno"],
  ["copy ", "copia texto para a área de transferência"], ["base64 encode ", "codifica texto"],
  ["base64 decode ", "decodifica texto"], ["url encode ", "codifica uma URL"],
  ["url decode ", "decodifica uma URL"], ["color ", "converte HEX para RGB"],
  ["uuid", "gera um UUID"], ["timestamp", "mostra ISO e Unix"], ["date", "mostra data local"],
  ["version", "mostra versões"], ["storage", "mostra o uso de armazenamento"],
  ["reload", "recarrega a página"], ["home", "volta à Home"],
  ["history", "mostra o histórico"], ["history clear", "remove o histórico"],
  ["history status", "mostra a política do histórico"], ["history off", "desativa a persistência"], ["history on", "ativa a persistência"], ["echo ", "imprime um texto"],
  ["modules reload", "recarrega manifestos"], ["enable ", "ativa um módulo"], ["disable ", "desativa um módulo"],
  ["git check ", "busca atualizações de um módulo"], ["git update ", "atualiza módulo sem mudanças locais"],
  ["portable", "abre a exportação portátil"],
  ["python --version", "mostra o Python encontrado"], ["python -m pip --version", "mostra o pip do Python encontrado"],
  ["python -m unittest discover -v", "executa testes Python"], ["pip --version", "usa o pip do Python encontrado"],
  ["git status", "mostra o estado do repositório"], ["git log --oneline -10", "mostra os últimos commits"],
  ["git branch", "lista branches"], ["git diff", "mostra alterações"], ["git remote -v", "lista remotos"],
  ["git add ", "adiciona arquivos ao stage"], ["git commit -m \"", "cria um commit"],
  ["git pull", "baixa alterações"], ["git push", "envia commits"], ["git fetch", "atualiza referências"],
];
const MODULE_COMMAND_ALIASES = {
  organizer: "organizador",
  notes: "notas-flutuantes",
  photos: "organizador-fotos",
  converter: "conversor-arquivos",
  bridge: "bridge",
  drive2: "ink-driver",
  "project-analyzer": "analisador-projetos",
  "project-reader": "leitor-projetos",
  writer: "ink-write",
  sheets: "ink-sheet",
  qrcode: "gerador-qrcode",
  json: "ink-json",
  palette: "ink-palette",
  diff: "ink-diff",
  base64: "ink-base64",
  terminal: "ink-terminal",
};

function ensureStyles() {
  if (document.querySelector('[data-workspace-terminal-style], link[href$="/core/components/terminal.css"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_URL;
  link.dataset.workspaceTerminalStyle = "true";
  document.head.append(link);
}

function escapeHtml(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function terminalMarkup({ embedded }) {
  return `
    ${embedded ? "" : `<button class="workspace-terminal-launcher" type="button" aria-label="Abrir terminal" title="Abrir terminal"><span aria-hidden="true">&gt;_</span></button>`}
    <section class="workspace-terminal ${embedded ? "is-embedded" : ""}" aria-label="Ink Terminal" ${embedded ? "" : "hidden"}>
      <header class="workspace-terminal-bar">
        <div class="workspace-terminal-dots" aria-hidden="true"><i></i><i></i><i></i></div>
        <div class="workspace-terminal-title"><strong>Ink Terminal</strong><span data-terminal-status>conectando…</span></div>
        <div class="workspace-terminal-actions">
          <button type="button" data-terminal-cancel aria-label="Cancelar processo" title="Cancelar processo" disabled>■</button>
          <button type="button" data-terminal-export aria-label="Exportar sessão" title="Exportar sessão">⇩</button>
          <button type="button" data-terminal-copy aria-label="Copiar última saída" title="Copiar última saída">⧉</button>
          <button type="button" data-terminal-clear aria-label="Limpar terminal" title="Limpar">⌫</button>
          ${embedded ? "" : `<button type="button" data-terminal-close aria-label="Fechar terminal" title="Fechar">×</button>`}
        </div>
      </header>
      <nav class="workspace-terminal-tabs" aria-label="Abas do terminal"><div data-terminal-tab-list></div><button type="button" data-terminal-new-tab aria-label="Nova aba" title="Nova aba">＋</button></nav>
      <div class="workspace-terminal-screen" role="log" aria-live="polite" aria-relevant="additions"></div>
      <form class="workspace-terminal-form" autocomplete="off">
        <span class="workspace-terminal-prompt" aria-hidden="true"><span class="terminal-user">ink</span><span>:</span><span class="terminal-path" data-terminal-path>…</span><span>&gt;</span></span>
        <textarea rows="1" spellcheck="false" aria-label="Comando do terminal" placeholder="comando PowerShell ou help"></textarea>
        <div class="workspace-terminal-suggestions" role="listbox" aria-label="Sugestões de comandos" hidden></div>
      </form>
      <footer class="workspace-terminal-footer"><span>Enter executa</span><span>Tab completa</span><span>Ctrl + C cancela</span><span>↑ ↓ histórico</span><span>Ctrl + L limpa</span></footer>
    </section>`;
}

export function mountTerminal({ target = document.body, embedded = false } = {}) {
  ensureStyles();
  const host = document.createElement("div");
  host.className = embedded ? "workspace-terminal-host is-embedded" : "workspace-terminal-host";
  host.innerHTML = terminalMarkup({ embedded });
  target.append(host);

  const panel = host.querySelector(".workspace-terminal");
  const launcher = host.querySelector(".workspace-terminal-launcher");
  const screen = host.querySelector(".workspace-terminal-screen");
  const form = host.querySelector(".workspace-terminal-form");
  const input = host.querySelector("textarea");
  const status = host.querySelector("[data-terminal-status]");
  const pathLabel = host.querySelector("[data-terminal-path]");
  const suggestionsRoot = host.querySelector(".workspace-terminal-suggestions");
  const tabList = host.querySelector("[data-terminal-tab-list]");
  const cancelButton = host.querySelector("[data-terminal-cancel]");
  let cwd = "";
  let busy = false;
  let readyStatus = "pronto";
  let lastOutput = "";
  let history = [];
  let historyIndex = 0;
  let modulesCache = [];
  let suggestions = [];
  let sessions = [];
  let activeSession = null;
  let sessionSequence = 0;
  let suggestionRequest = 0;
  let suggestionTimer = 0;
  const pendingTerminalErrors = [];

  try { history = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]").filter((item) => typeof item === "string").slice(-HISTORY_LIMIT); } catch { history = []; }
  historyIndex = history.length;

  function renderTabs() {
    tabList.innerHTML = sessions.map((session) => `<span class="workspace-terminal-tab ${session === activeSession ? "active" : ""} ${session.busy ? "running" : ""} ${session.failed ? "failed" : ""}"><button type="button" data-terminal-tab="${session.id}" title="${escapeHtml(session.title)}">${session.busy ? "● " : ""}${escapeHtml(session.title)}</button><button type="button" data-terminal-tab-close="${session.id}" aria-label="Fechar ${escapeHtml(session.title)}">×</button></span>`).join("");
  }

  function captureSession() {
    if (!activeSession) return;
    activeSession.cwd = cwd;
    activeSession.history = [...history];
    activeSession.historyIndex = historyIndex;
    activeSession.lastOutput = lastOutput;
    activeSession.input = input.value;
  }

  function activateSession(session) {
    if (!session || session === activeSession || busy) return;
    captureSession();
    if (activeSession?.view) activeSession.view.hidden = true;
    activeSession = session;
    cwd = session.cwd;
    history = [...session.history];
    historyIndex = session.historyIndex;
    lastOutput = session.lastOutput;
    input.value = session.input;
    session.view.hidden = false;
    setCwd(cwd);
    refreshActiveStatus(); autoGrow(); renderTabs(); input.focus();
  }

  function createSession(initialCwd = cwd) {
    if (busy) return null;
    captureSession();
    if (activeSession?.view) activeSession.view.hidden = true;
    const view = document.createElement("div");
    view.className = "workspace-terminal-session";
    screen.append(view);
    const session = {
      id: `terminal-${++sessionSequence}`, title: `Terminal ${sessionSequence}`, cwd: initialCwd,
      history: [...history], historyIndex: history.length, lastOutput: "", input: "", view, logLines: [],
      busy: false, failed: false, executionId: "", pid: null, startedAt: 0, stdoutCount: 0, stderrCount: 0,
      durationMs: 0, exitCode: null, resources: {}, pollTimer: 0, command: "",
    };
    sessions.push(session);
    activeSession = session;
    cwd = initialCwd; history = [...session.history]; historyIndex = history.length; lastOutput = ""; input.value = "";
    setCwd(cwd); refreshActiveStatus(); renderTabs(); intro(session); input.focus();
    return session;
  }

  function closeSession(session) {
    if (!session || busy) return;
    if (session.busy) {
      append("Cancele o processo antes de fechar esta aba.", "meta", session);
      return;
    }
    const index = sessions.indexOf(session);
    if (index < 0) return;
    if (sessions.length === 1) { clear(session); activeSession.title = "Terminal 1"; renderTabs(); return; }
    if (session === activeSession) {
      captureSession();
      sessions.splice(index, 1);
      session.view.remove();
      activeSession = null;
      activateSession(sessions[Math.min(index, sessions.length - 1)]);
    } else {
      sessions.splice(index, 1);
      session.view.remove();
    }
    renderTabs();
  }

  function appendBlackBoxError(title = "Erro no Terminal", detail = "", session = activeSession) {
    const log = [title, detail].filter(Boolean).join("\n");
    if (!session) return null;
    session.lastOutput = log;
    session.logLines.push(`[erro] ${log}`);
    if (session === activeSession) lastOutput = log;

    const box = document.createElement("details");
    box.className = "workspace-terminal-blackbox";
    const summary = document.createElement("summary");
    summary.textContent = "caixa preta: erro";
    const output = document.createElement("pre");
    output.textContent = log;
    box.append(summary, output);
    session.view.append(box);
    screen.scrollTop = screen.scrollHeight;

    return box;
  }

  function rememberTerminalError(command, cwdValue, stderr) {
    const detail = stderr.slice(-6).join("\n");
    pendingTerminalErrors.push({
      title: `Falha no Terminal: ${command.split(/\s+/, 1)[0]}`,
      cwd: cwdValue,
      detail,
    });
    window.setTimeout(() => {
      const index = pendingTerminalErrors.findIndex((item) => item.cwd === cwdValue && item.detail === detail);
      if (index >= 0) pendingTerminalErrors.splice(index, 1);
    }, 5000);
  }

  function append(text = "", type = "", session = activeSession) {
    if (!session) return null;
    if (type.split(/\s+/).includes("error")) return appendBlackBoxError("Erro no Terminal", text, session);
    const line = document.createElement("div");
    line.className = `workspace-terminal-line ${type}`.trim();
    line.textContent = String(text);
    session.view.append(line);
    session.logLines.push(String(text));
    session.logLines = session.logLines.slice(-5000);
    screen.scrollTop = screen.scrollHeight;
    return line;
  }

  function appendCommand(command, session = activeSession) {
    if (!session) return;
    const line = document.createElement("div");
    line.className = "workspace-terminal-line command";
    const prompt = document.createElement("span");
    prompt.className = "terminal-command-prompt";
    prompt.textContent = `${shortPath(session.cwd)}> `;
    line.append(prompt, document.createTextNode(command));
    session.view.append(line);
    session.logLines.push(`${session.cwd}> ${command}`);
    screen.scrollTop = screen.scrollHeight;
  }

  function shortPath(value) {
    if (!value) return "…";
    const pieces = value.replaceAll("\\", "/").split("/").filter(Boolean);
    return pieces.length > 2 ? `…/${pieces.slice(-2).join("/")}` : value;
  }

  function setCwd(value) {
    cwd = value || cwd;
    if (activeSession) activeSession.cwd = cwd;
    pathLabel.textContent = shortPath(cwd);
    pathLabel.title = cwd;
  }

  function clear(session = activeSession) {
    if (!session) return;
    session.view.replaceChildren();
    session.logLines = [];
    session.lastOutput = "";
    if (session === activeSession) lastOutput = "";
  }

  function intro(session = activeSession) {
    append("Ink Terminal", "accent", session);
    append("Digite help para ver os comandos do Workspace ou execute um comando do PowerShell.", "meta", session);
    append("", "", session);
  }

  function open() {
    panel.hidden = false;
    launcher?.setAttribute("aria-expanded", "true");
    requestAnimationFrame(() => input.focus());
  }

  function close() {
    if (embedded) return;
    panel.hidden = true;
    launcher?.setAttribute("aria-expanded", "false");
  }

  async function api(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    const method = String(options.method || "GET").toUpperCase();
    const protectedRead = method === "GET" && /^\/api\/terminal\/(?:processes\/|completions|audit)/.test(path);
    return apiRequest(path, { ...options, headers, authenticated: protectedRead });
  }

  function clean(value) {
    return String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
  }

  function moduleCommandName(module) {
    return MODULE_COMMAND_ALIASES[module?.id] || module?.id || "";
  }

  function findModule(query) {
    const wanted = clean(query).replaceAll(" ", "-");
    return modulesCache.find((module) => {
      const candidates = [module.id, module.name, moduleCommandName(module)].map((value) => clean(value));
      return candidates.some((value) => value === wanted || value.replaceAll("-", "") === wanted.replaceAll("-", ""));
    });
  }

  function moduleSuggestions(prefix, verb) {
    const query = clean(prefix);
    return modulesCache
      .filter((module) => !query || clean(`${module.id} ${moduleCommandName(module)} ${module.name}`).includes(query))
      .slice(0, 7)
      .map((module) => ({ value: `${verb} ${moduleCommandName(module)}`, description: module.name }));
  }

  function candidateSuggestions(raw) {
    const value = raw.trimStart();
    const lower = clean(value);
    const argumentSets = {
      "theme ": ["light", "dark", "system"],
      "density ": ["compact", "comfortable", "spacious"],
      "font ": ["small", "comfortable", "large"],
      "config ": ["bridge", "ink-driver"],
      "python ": ["--version", "-m pip --version", "-m unittest discover -v"],
      "pip ": ["--version", "list"],
    };
    for (const [prefix, values] of Object.entries(argumentSets)) {
      if (lower.startsWith(prefix)) {
        const typed = lower.slice(prefix.length);
        return values.filter((item) => item.startsWith(typed)).map((item) => ({ value: `${prefix}${item}`, description: "opção disponível" }));
      }
    }
    for (const verb of ["open", "find", "ping", "start", "stop", "favorite", "unfavorite", "enable", "disable"]) {
      const prefix = `${verb} `;
      if (lower.startsWith(prefix)) return moduleSuggestions(value.slice(prefix.length), verb);
    }
    for (const verb of ["git check", "git update"]) {
      const prefix = `${verb} `;
      if (lower.startsWith(prefix)) return moduleSuggestions(value.slice(prefix.length), verb);
    }
    if (lower.startsWith("git ")) {
      return COMMANDS.filter(([command]) => command.startsWith("git ") && clean(command).startsWith(lower)).slice(0, 7).map(([command, description]) => ({ value: command, description }));
    }
    if (!value || value.includes(" ")) return [];
    return COMMANDS
      .filter(([command]) => clean(command).startsWith(lower))
      .slice(0, 7)
      .map(([command, description]) => ({ value: command, description }));
  }

  function hideSuggestions() {
    suggestionRequest += 1;
    window.clearTimeout(suggestionTimer);
    suggestions = [];
    suggestionsRoot.hidden = true;
    suggestionsRoot.replaceChildren();
  }

  function renderSuggestions(items) {
    suggestions = items;
    suggestionsRoot.replaceChildren();
    if (!suggestions.length) return hideSuggestions();
    suggestions.forEach((suggestion, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", "option");
      button.dataset.suggestionIndex = String(index);
      const command = document.createElement("code"); command.textContent = suggestion.value;
      const description = document.createElement("span"); description.textContent = suggestion.description;
      button.append(command, description);
      suggestionsRoot.append(button);
    });
    suggestionsRoot.hidden = false;
  }

  function updateSuggestions() {
    const value = input.value;
    const local = candidateSuggestions(value);
    renderSuggestions(local);
    const requestId = ++suggestionRequest;
    window.clearTimeout(suggestionTimer);
    suggestionTimer = window.setTimeout(async () => {
      try {
        const query = new URLSearchParams({ prefix: value, cwd: activeSession?.cwd || cwd });
        const payload = await api(`/api/terminal/completions?${query}`);
        if (requestId !== suggestionRequest || input.value !== value) return;
        const combined = [...local, ...(payload.items || [])].filter((item, index, all) => (
          all.findIndex((candidate) => candidate.value.toLocaleLowerCase("pt-BR") === item.value.toLocaleLowerCase("pt-BR")) === index
        )).slice(0, 8);
        renderSuggestions(combined);
      } catch { /* autocomplete local continua disponível */ }
    }, 140);
  }

  function acceptSuggestion(index = 0) {
    const suggestion = suggestions[index];
    if (!suggestion) return false;
    input.value = suggestion.value;
    input.setSelectionRange(input.value.length, input.value.length);
    autoGrow();
    updateSuggestions();
    return true;
  }

  async function workspaceCommand(raw) {
    const normalized = raw.trim().toLocaleLowerCase("pt-BR");
    if (normalized === "help") {
      [
        "Comandos do Workspace:",
        "  help                         lista esta ajuda",
        "  clear                        limpa a tela",
        "  subdivide                    divide a tela atual em duas instâncias",
        "  unsubidivide                 escolhe uma tela e fecha a outra",
        "  modules                      lista os módulos",
        "  modules reload               recarrega manifestos novos",
        "  enable|disable <módulo>      ativa ou desativa um módulo",
        "  git check|update <módulo>    verifica ou aplica atualização segura",
        "  portable                     abre o modo portátil",
        "  status                       mostra a saúde do ecossistema",
        "  settings                     mostra as preferências globais",
        "  favorites                    lista os módulos favoritos",
        "  favorite <módulo>            adiciona um favorito",
        "  unfavorite <módulo>          remove um favorito",
        "  open <módulo>                abre um módulo pelo nome ou ID",
        "  open home|modules|settings   abre uma seção da Home",
        "  theme light|dark|system      altera o tema global",
        "  accent #RRGGBB               altera a cor principal",
        "  density compact|comfortable|spacious",
        "  font small|comfortable|large",
        "  start|stop <módulo>          controla um serviço gerenciado",
        "  drop                         abre a Drop Zone",
        "  clipboard                    abre o clipboard interno",
        "  clip add <texto>             guarda texto para outros módulos",
        "  recent                       lista os arquivos recebidos",
        "  find|ping <módulo>           procura ou verifica uma ferramenta",
        "  diagnostics                  detalha navegador, storage e módulos",
        "  config bridge|ink-driver     abre a configuração correspondente",
        "  python <arquivo|opção>       usa .venv/venv local ou o Python do computador",
        "  pip <opção>                  usa o pip do mesmo Python encontrado",
        "  copy <texto>                 copia texto",
        "  base64 encode|decode <texto> transforma texto em Base64",
        "  url encode|decode <texto>    codifica ou decodifica URL",
        "  color #RRGGBB                mostra a cor em RGB",
        "  storage                      mostra uso de armazenamento",
        "  uuid                         gera um UUID",
        "  timestamp                    mostra horário ISO e Unix",
        "  date | version | reload      utilitários da sessão",
        "  history [status|clear|off|on] mostra, limpa ou controla o histórico",
        "  git status|log|branch|diff   comandos Git funcionam diretamente",
        "  qualquer comando do PC       é executado na pasta atual",
        "",
        "Atalhos: Enter executa · Tab completa · Shift+Enter quebra linha · Ctrl+L limpa · ↑/↓ histórico",
      ].forEach((line) => append(line, line.endsWith(":") ? "accent" : ""));
      return true;
    }
    if (normalized === "clear" || normalized === "cls") { clear(); return true; }
    if (normalized === "subdivide") {
      const result = await subdivideView();
      append(result.message, result.ok ? "success" : "meta");
      return true;
    }
    if (normalized === "unsubidivide" || normalized === "unsubdivide") {
      const result = await unSubdivideView();
      append(result.message, result.ok ? "success" : "meta");
      return true;
    }
    if (normalized === "history") { history.forEach((item, index) => append(`${String(index + 1).padStart(3, " ")}  ${item}`)); return true; }
    if (normalized === "history status") {
      append(`Persistência: ${localStorage.getItem(HISTORY_ENABLED_KEY) === "false" ? "desativada" : "ativada"} · ${history.length}/${HISTORY_LIMIT} comandos.`, "meta");
      append("Comandos com indícios de credenciais não são armazenados.", "meta");
      return true;
    }
    if (normalized === "history clear") {
      if (!globalThis.confirm("Remover somente o histórico de comandos do Ink Terminal?")) { append("Limpeza cancelada.", "meta"); return true; }
      history = []; historyIndex = 0; localStorage.removeItem(HISTORY_KEY); append("Histórico do Ink Terminal removido com segurança.", "success"); return true;
    }
    if (normalized === "history off") {
      localStorage.setItem(HISTORY_ENABLED_KEY, "false"); localStorage.removeItem(HISTORY_KEY); history = []; historyIndex = 0;
      append("Persistência do histórico desativada.", "success"); return true;
    }
    if (normalized === "history on") {
      localStorage.setItem(HISTORY_ENABLED_KEY, "true"); append("Persistência do histórico ativada.", "success"); return true;
    }
    if (normalized === "uuid") { append(crypto.randomUUID(), "success"); return true; }
    if (normalized === "timestamp") { const now = new Date(); append(now.toISOString()); append(String(Math.floor(now.getTime() / 1000))); return true; }
    if (normalized === "date") { append(new Date().toLocaleString("pt-BR", { dateStyle: "full", timeStyle: "medium" })); return true; }
    if (normalized === "home" || normalized === "open home") { location.assign(coreUrl("/")); return true; }
    if (normalized === "reload") { location.reload(); return true; }
    if (normalized.startsWith("echo ")) { append(raw.trim().slice(5)); return true; }
    if (normalized.startsWith("copy ")) {
      try { await navigator.clipboard.writeText(raw.trim().slice(5)); append("Texto copiado.", "success"); }
      catch (error) { append(error.message, "error"); }
      return true;
    }
    if (normalized.startsWith("base64 encode ") || normalized.startsWith("base64 decode ")) {
      try {
        const decoding = normalized.startsWith("base64 decode ");
        const value = raw.trim().slice(decoding ? 14 : 14);
        const result = decoding
          ? new TextDecoder().decode(Uint8Array.from(atob(value), (character) => character.charCodeAt(0)))
          : btoa(String.fromCharCode(...new TextEncoder().encode(value)));
        append(result, "success");
      } catch { append("Não foi possível transformar esse texto em Base64.", "error"); }
      return true;
    }
    if (normalized.startsWith("url encode ") || normalized.startsWith("url decode ")) {
      try {
        const decoding = normalized.startsWith("url decode ");
        const value = raw.trim().slice(decoding ? 11 : 11);
        append(decoding ? decodeURIComponent(value) : encodeURIComponent(value), "success");
      } catch { append("URL codificada inválida.", "error"); }
      return true;
    }
    if (normalized.startsWith("color ")) {
      const value = raw.trim().slice(6).trim();
      const match = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(value);
      if (!match) append("Use: color #RRGGBB", "error");
      else append(`rgb(${Number.parseInt(match[1], 16)}, ${Number.parseInt(match[2], 16)}, ${Number.parseInt(match[3], 16)})`, "success");
      return true;
    }
    if (normalized === "drop") { globalThis.WorkspaceDropzone?.open(); append("Drop Zone aberta.", "success"); return true; }
    if (normalized === "clipboard") { globalThis.WorkspaceActivity?.open("clipboard"); append("Clipboard interno aberto.", "success"); return true; }
    if (normalized.startsWith("clip add ")) {
      try {
        const response = await api("/api/clipboard", { method: "POST", body: JSON.stringify({ text: raw.trim().slice(9), source: "Ink Terminal" }) });
        append(`Texto adicionado: ${response.id}`, "success");
      } catch (error) { append(error.message, "error"); }
      return true;
    }
    if (normalized.startsWith("theme ")) {
      const theme = normalized.slice(6).trim();
      if (!["light", "dark", "system"].includes(theme)) append("Use: theme light, theme dark ou theme system", "error");
      else {
        try { await Settings.set("theme", theme); append(`Tema alterado para ${theme}.`, "success"); }
        catch (error) { append(error.message, "error"); }
      }
      return true;
    }
    if (normalized.startsWith("accent ")) {
      const accent = raw.trim().slice(7).trim();
      if (!/^#[0-9a-f]{6}$/i.test(accent)) append("Use: accent #RRGGBB", "error");
      else { try { await Settings.set("accent", accent); append(`Cor principal alterada para ${accent}.`, "success"); } catch (error) { append(error.message, "error"); } }
      return true;
    }
    if (normalized.startsWith("density ")) {
      const density = normalized.slice(8).trim();
      if (!["compact", "comfortable", "spacious"].includes(density)) append("Use: density compact, comfortable ou spacious", "error");
      else { try { await Settings.set("density", density); append(`Densidade alterada para ${density}.`, "success"); } catch (error) { append(error.message, "error"); } }
      return true;
    }
    if (normalized.startsWith("font ")) {
      const font = normalized.slice(5).trim();
      if (!["small", "comfortable", "large"].includes(font)) append("Use: font small, comfortable ou large", "error");
      else { try { await Settings.set("font_size", font); append(`Tamanho de texto alterado para ${font}.`, "success"); } catch (error) { append(error.message, "error"); } }
      return true;
    }
    if (normalized === "settings") {
      const settings = Settings.get();
      ["theme", "accent", "language", "density", "font_size", "high_contrast", "reduce_motion"].forEach((key) => append(`${key.padEnd(18)} ${settings[key]}`));
      return true;
    }
    if (normalized === "version") {
      try {
        const [health, terminal] = await Promise.all([api("/api/health"), api("/api/terminal/health")]);
        append(`Workspace OS ${health.version}`, "success");
        append(`Python: ${terminal.pythonAvailable ? terminal.pythonExecutable : "não encontrado"}`, terminal.pythonAvailable ? "success" : "error");
        append(`Navegador ${navigator.userAgent}`);
      }
      catch (error) { append(error.message, "error"); }
      return true;
    }
    if (normalized === "storage") {
      try {
        const estimate = await navigator.storage?.estimate?.();
        if (!estimate) append("Estimativa de armazenamento indisponível.", "meta");
        else {
          const mb = (value) => `${(Number(value || 0) / 1024 / 1024).toFixed(1)} MB`;
          append(`Em uso: ${mb(estimate.usage)}`, "success");
          append(`Cota do navegador: ${mb(estimate.quota)}`);
        }
      } catch (error) { append(error.message, "error"); }
      return true;
    }
    if (normalized === "recent") {
      try {
        const payload = await api("/api/dropzone/history");
        const items = payload.items || [];
        if (!items.length) append("Nenhum arquivo recente na Drop Zone.", "meta");
        items.slice(0, 15).forEach((item) => append(`${item.kind === "folder" ? "[DIR]" : "[FILE]"} ${item.name}`));
      } catch (error) { append(error.message, "error"); }
      return true;
    }
    if (normalized === "diagnostics") {
      try {
        const [health, payload] = await Promise.all([api("/api/health"), api("/api/modules")]);
        modulesCache = payload.modules || [];
        append(`Core ${health.status} · ${health.version}`, "success");
        append(`Navegador: ${navigator.onLine ? "online" : "offline"} · BroadcastChannel: ${"BroadcastChannel" in globalThis ? "sim" : "não"}`);
        append(`localStorage: ${(() => { try { localStorage.setItem("workspace.terminal.probe", "1"); localStorage.removeItem("workspace.terminal.probe"); return "ok"; } catch { return "indisponível"; } })()}`);
        modulesCache.forEach((module) => append(`${module.reachable || module.kind === "static-web" ? "[ok]" : "[--]"} ${moduleCommandName(module)}`));
      } catch (error) { append(error.message, "error"); }
      return true;
    }
    if (["config bridge", "config driver", "config ink-driver", "config inkdriver"].includes(normalized)) {
      const bridge = normalized.endsWith("bridge");
      if (location.port === "8790") {
        document.querySelector('[data-route="settings"]')?.click();
        window.setTimeout(() => document.querySelector(bridge ? "#bridge-host" : "#drive-url")?.scrollIntoView({ behavior: "smooth", block: "center" }), 80);
      } else location.assign(coreUrl("/#settings"));
      append(`Abrindo configuração do ${bridge ? "Bridge" : "InkDriver"}.`, "success");
      return true;
    }
    if (normalized === "status") {
      try {
        const [health, payload] = await Promise.all([api("/api/health"), api("/api/modules")]);
        const online = payload.modules.filter((module) => module.reachable || module.kind === "static-web").length;
        append(`Core ${health.status} · versão ${health.version}`, "success");
        append(`${online}/${payload.modules.length} módulos disponíveis`);
      } catch (error) { append(error.message, "error"); }
      return true;
    }
    if (normalized === "modules") {
      try {
        const payload = await api("/api/modules");
        modulesCache = payload.modules || [];
        payload.modules.forEach((module) => append(`${module.reachable || module.kind === "static-web" ? "[ok]" : "[--]"} ${moduleCommandName(module).padEnd(20)} ${module.name}`));
      } catch (error) { append(error.message, "error"); }
      return true;
    }
    if (normalized === "modules reload") {
      try { const result = await api("/api/modules/reload", { method: "POST", body: "{}" }); append(`${result.modules} módulos recarregados.`, "success"); }
      catch (error) { append(error.message, "error"); }
      return true;
    }
    if (normalized === "portable") {
      location.assign(coreUrl("/#settings"));
      append("Abrindo o modo portátil.", "success");
      return true;
    }
    if (normalized.startsWith("enable ") || normalized.startsWith("disable ")) {
      const action = normalized.startsWith("enable ") ? "enable" : "disable";
      const query = normalized.slice(action.length + 1).trim();
      const module = findModule(query);
      const moduleId = module?.id || query;
      try { await api(`/api/modules/${encodeURIComponent(moduleId)}/${action}`, { method: "POST", body: "{}" }); append(`${module?.name || query}: ${action === "enable" ? "ativado" : "desativado"}.`, "success"); }
      catch (error) { append(error.message, "error"); }
      return true;
    }
    if (normalized.startsWith("git check ") || normalized.startsWith("git update ")) {
      const updating = normalized.startsWith("git update ");
      const query = normalized.slice(updating ? 11 : 10).trim();
      const moduleId = findModule(query)?.id || query;
      try {
        const result = await api(`/api/modules/${encodeURIComponent(moduleId)}/${updating ? "git-update" : "git-status"}`, { method: "POST", body: JSON.stringify({ fetch: !updating }) });
        const status = result.status || result;
        append(result.message || `${status.branch}: ${status.ahead} à frente · ${status.behind} atrás${status.dirty ? " · alterações locais" : ""}`, status.dirty ? "error" : "success");
      } catch (error) { append(error.message, "error"); }
      return true;
    }
    if (normalized.startsWith("find ") || normalized.startsWith("ping ")) {
      const isPing = normalized.startsWith("ping ");
      const query = raw.trim().slice(isPing ? 5 : 5).trim();
      try {
        const payload = await api("/api/modules");
        modulesCache = payload.modules || [];
        const found = modulesCache.filter((module) => clean(`${module.id} ${moduleCommandName(module)} ${module.name} ${module.description}`).includes(clean(query)));
        if (!found.length) append(`Nenhum módulo encontrado para: ${query}`, "error");
        else if (isPing) found.slice(0, 1).forEach((module) => append(`${module.name}: ${module.reachable || module.kind === "static-web" ? "disponível" : "indisponível"}`, module.reachable || module.kind === "static-web" ? "success" : "error"));
        else found.forEach((module) => append(`${moduleCommandName(module).padEnd(20)} ${module.name}`));
      } catch (error) { append(error.message, "error"); }
      return true;
    }
    if (normalized === "favorites" || normalized.startsWith("favorite ") || normalized.startsWith("unfavorite ")) {
      try {
        const payload = await api("/api/modules");
        const clean = (value) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
        const favorites = new Set(Settings.get("favorite_modules") || []);
        if (normalized !== "favorites") {
          const removing = normalized.startsWith("unfavorite ");
          const query = raw.trim().slice(removing ? 11 : 9).trim();
          modulesCache = payload.modules || [];
          const found = findModule(query) || payload.modules.find((module) => clean(module.name).includes(clean(query)));
          if (!found) append(`Módulo não encontrado: ${query}`, "error");
          else {
            if (removing) favorites.delete(found.id); else favorites.add(found.id);
            await Settings.set("favorite_modules", [...favorites]);
            append(`${found.name} ${removing ? "removido dos" : "adicionado aos"} favoritos.`, "success");
          }
        } else {
          const names = payload.modules.filter((module) => favorites.has(module.id)).map((module) => module.name);
          (names.length ? names : ["Nenhum favorito."]).forEach((name) => append(name));
        }
      } catch (error) { append(error.message, "error"); }
      return true;
    }
    if (normalized.startsWith("start ") || normalized.startsWith("stop ")) {
      const action = normalized.startsWith("start ") ? "start" : "stop";
      const query = normalized.slice(action.length + 1).trim();
      const module = findModule(query);
      const moduleId = module?.id || query;
      try { const result = await api(`/api/modules/${encodeURIComponent(moduleId)}/${action}`, { method: "POST", body: "{}" }); append(result.message || `${module?.name || query}: ${action}`, "success"); }
      catch (error) { append(error.message, "error"); }
      return true;
    }
    if (normalized.startsWith("open ")) {
      const query = normalized.slice(5).trim();
      const routeAliases = { home: "dashboard", inicio: "dashboard", dashboard: "dashboard", modules: "modules", modulos: "modules", settings: "settings", configuracoes: "settings", diagnostics: "diagnostics", diagnostico: "diagnostics" };
      if (routeAliases[query] && location.port === "8790") {
        document.querySelector(`[data-route="${routeAliases[query]}"]`)?.click();
        append(`Abrindo ${query}.`, "success");
        return true;
      }
      try {
        const payload = await api("/api/modules");
        modulesCache = payload.modules || [];
        const clean = (value) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
        const found = findModule(query) || payload.modules.find((module) => clean(module.name).includes(clean(query)));
        if (!found?.url) append(`Módulo não encontrado ou sem endereço: ${query}`, "error");
        else { append(`Abrindo ${found.name}.`, "success"); location.assign(found.url); }
      } catch (error) { append(error.message, "error"); }
      return true;
    }
    return false;
  }

  function formatBytes(value) {
    if (!Number.isFinite(Number(value))) return "recursos n/d";
    const bytes = Number(value);
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function formatDuration(value) {
    const milliseconds = Number(value || 0);
    return milliseconds < 1000 ? `${milliseconds} ms` : `${(milliseconds / 1000).toFixed(1)} s`;
  }

  function refreshActiveStatus() {
    const session = activeSession;
    cancelButton.disabled = !session?.busy;
    cancelButton.classList.toggle("is-active", Boolean(session?.busy));
    form.classList.toggle("is-busy", Boolean(busy || session?.busy));
    if (!session?.busy) {
      status.textContent = readyStatus;
      return;
    }
    const memory = session.resources?.workingSetBytes ?? session.resources?.peakWorkingSetBytes;
    status.textContent = `PID ${session.pid || "…"} · ${formatDuration(session.durationMs)} · ${formatBytes(memory)}`;
  }

  function setSessionCwd(session, value) {
    session.cwd = value || session.cwd;
    if (session === activeSession) setCwd(session.cwd);
  }

  function consumeExecutionOutput(session, result) {
    const stdout = result.stdout || [];
    const stderr = result.stderr || [];
    stdout.slice(session.stdoutCount).forEach((line) => append(line, "", session));
    stderr.slice(session.stderrCount).forEach((line) => append(line, "stderr", session));
    session.stdoutCount = stdout.length;
    session.stderrCount = stderr.length;
    session.lastOutput = [...stdout, ...stderr].join("\n");
    if (session === activeSession) lastOutput = session.lastOutput;
  }

  function finishExecution(session, result) {
    consumeExecutionOutput(session, result);
    session.busy = false;
    session.durationMs = result.durationMs || session.durationMs;
    session.exitCode = result.exitCode;
    session.resources = result.resources || session.resources;
    session.failed = result.status !== "cancelled" && !result.ok;
    window.clearTimeout(session.pollTimer);
    if (result.outputTruncated) append("A saída excedeu o limite local e foi truncada.", "meta", session);
    const memory = result.resources?.peakWorkingSetBytes ?? result.resources?.workingSetBytes;
    const cpu = Number.isFinite(Number(result.resources?.cpuSeconds)) ? `${result.resources.cpuSeconds} s CPU` : "CPU n/d";
    if (result.status === "cancelled") {
      append(`processo cancelado · PID ${result.pid} · ${formatDuration(result.durationMs)} · ${formatBytes(memory)} · ${cpu}`, "meta", session);
    } else if (result.status === "timed_out") {
      appendBlackBoxError("Processo encerrado por tempo limite", `${session.command}\nPID ${result.pid}\nduração: ${formatDuration(result.durationMs)}`, session);
    } else if (!result.ok) {
      rememberTerminalError(session.command, result.cwd, result.stderr || []);
      appendBlackBoxError(
        `Comando terminou com código ${result.exitCode}`,
        [session.command, ...(result.stderr || []), `PID: ${result.pid || "n/d"}`, `duração: ${formatDuration(result.durationMs)}`].join("\n"),
        session,
      );
    } else {
      append(`finalizado · PID ${result.pid || "interno"} · código ${result.exitCode} · ${formatDuration(result.durationMs)} · ${formatBytes(memory)} · ${cpu}`, "success meta", session);
    }
    renderTabs();
    if (session === activeSession) refreshActiveStatus();
  }

  async function pollExecution(session) {
    if (!session.busy || !session.executionId) return;
    try {
      const result = await api(`/api/terminal/processes/${encodeURIComponent(session.executionId)}`);
      session.pollFailures = 0;
      session.durationMs = result.durationMs;
      session.resources = result.resources || {};
      consumeExecutionOutput(session, result);
      if (result.status === "running") {
        if (session === activeSession) refreshActiveStatus();
        session.pollTimer = window.setTimeout(() => pollExecution(session), 350);
      } else finishExecution(session, result);
    } catch (error) {
      session.pollFailures = (session.pollFailures || 0) + 1;
      if (session.pollFailures < 4) session.pollTimer = window.setTimeout(() => pollExecution(session), 750);
      else {
        session.busy = false;
        session.failed = true;
        appendBlackBoxError("Falha ao acompanhar o processo", error?.message || String(error), session);
        renderTabs();
        if (session === activeSession) refreshActiveStatus();
      }
    }
  }

  async function cancelExecution(session = activeSession) {
    if (!session?.busy || !session.executionId) return;
    if (session === activeSession) status.textContent = `cancelando PID ${session.pid}…`;
    try {
      const result = await api(`/api/terminal/processes/${encodeURIComponent(session.executionId)}`, { method: "DELETE" });
      session.durationMs = result.durationMs;
      session.resources = result.resources || session.resources;
      if (result.status !== "running") finishExecution(session, result);
    } catch (error) {
      appendBlackBoxError("Não foi possível cancelar o processo", error?.message || String(error), session);
    }
  }

  async function execute(raw) {
    const command = raw.trim();
    if (!command || busy || activeSession?.busy) return;
    const session = activeSession;
    if (!session) return;
    busy = true;
    refreshActiveStatus();
    if (session.title.startsWith("Terminal ")) { session.title = command.slice(0, 22); renderTabs(); }
    hideSuggestions();
    appendCommand(command, session);
    const historyEnabled = localStorage.getItem(HISTORY_ENABLED_KEY) !== "false";
    if (!SENSITIVE_COMMAND.test(command) && history.at(-1) !== command) history.push(command);
    history = history.slice(-HISTORY_LIMIT);
    historyIndex = history.length;
    session.history = [...history];
    session.historyIndex = historyIndex;
    try { if (historyEnabled && !SENSITIVE_COMMAND.test(command)) localStorage.setItem(HISTORY_KEY, JSON.stringify(history)); } catch { /* histórico opcional */ }
    try {
      if (await workspaceCommand(command)) return;
      const request = { command, cwd: session.cwd, sessionId: session.id };
      const result = await api("/api/terminal/processes", { method: "POST", body: JSON.stringify(request) });
      setSessionCwd(session, result.cwd);
      session.command = command;
      session.executionId = result.executionId || "";
      session.pid = result.pid;
      session.startedAt = Date.now();
      session.durationMs = result.durationMs || 0;
      session.resources = result.resources || {};
      session.stdoutCount = 0;
      session.stderrCount = 0;
      session.failed = false;
      if (result.status === "running" && result.executionId) {
        session.busy = true;
        append(`iniciado · PID ${result.pid}`, "meta", session);
        renderTabs();
        pollExecution(session);
      } else finishExecution(session, result);
    } catch (error) {
      session.failed = true;
      appendBlackBoxError("Falha no Terminal", `${command}\n${error?.stack || error?.message || String(error)}`, session);
    } finally {
      busy = false;
      refreshActiveStatus();
      input.focus();
    }
  }

  function autoGrow() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
  }

  function exportSession(session = activeSession) {
    if (!session) return;
    const metadata = [
      "Ink Terminal — log de sessão",
      `Sessão: ${session.title}`,
      `Diretório: ${session.cwd || "n/d"}`,
      `Exportado em: ${new Date().toISOString()}`,
      `Último PID: ${session.pid || "n/d"}`,
      `Último código de saída: ${session.exitCode ?? "n/d"}`,
      `Última duração: ${formatDuration(session.durationMs)}`,
      "",
    ];
    const blob = new Blob([[...metadata, ...session.logLines].join("\n")], { type: "text/plain;charset=utf-8" });
    const link = document.createElement("a");
    const stamp = new Date().toISOString().replaceAll(":", "-").replace(/\.\d{3}Z$/, "Z");
    link.href = URL.createObjectURL(blob);
    link.download = `ink-terminal-${session.id}-${stamp}.log`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    append("Log da sessão exportado.", "success meta", session);
  }

  launcher?.addEventListener("click", () => panel.hidden ? open() : close());
  host.querySelector("[data-terminal-new-tab]").addEventListener("click", () => createSession(cwd));
  tabList.addEventListener("click", (event) => {
    const closeButton = event.target.closest("[data-terminal-tab-close]");
    if (closeButton) {
      event.stopPropagation();
      closeSession(sessions.find((session) => session.id === closeButton.dataset.terminalTabClose));
      return;
    }
    const button = event.target.closest("[data-terminal-tab]");
    if (button) activateSession(sessions.find((session) => session.id === button.dataset.terminalTab));
  });
  function eventIsInsideTerminal(event) {
    const path = typeof event.composedPath === "function" ? event.composedPath() : [];
    return path.includes(panel) || (launcher && path.includes(launcher)) || panel.contains(event.target) || launcher?.contains(event.target);
  }
  document.addEventListener("pointerdown", (event) => {
    if (!embedded && !panel.hidden && !eventIsInsideTerminal(event)) close();
  });
  document.addEventListener("click", (event) => {
    if (!embedded && !panel.hidden && !eventIsInsideTerminal(event)) close();
  });
  host.querySelector("[data-terminal-close]")?.addEventListener("click", close);
  host.querySelector("[data-terminal-clear]").addEventListener("click", () => { clear(); intro(); input.focus(); });
  cancelButton.addEventListener("click", () => cancelExecution());
  host.querySelector("[data-terminal-export]").addEventListener("click", () => exportSession());
  host.querySelector("[data-terminal-copy]").addEventListener("click", async () => {
    const output = activeSession?.lastOutput || lastOutput;
    if (!output) return append("Não há saída para copiar.", "meta");
    try { await navigator.clipboard.writeText(output); append("Última saída copiada.", "success meta"); }
    catch { append("Não foi possível copiar a saída.", "error"); }
  });
  suggestionsRoot.addEventListener("pointerdown", (event) => event.preventDefault());
  suggestionsRoot.addEventListener("click", (event) => {
    const button = event.target.closest("[data-suggestion-index]");
    if (button) { acceptSuggestion(Number(button.dataset.suggestionIndex)); input.focus(); }
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (activeSession?.busy || busy) return;
    const value = input.value; input.value = ""; hideSuggestions(); autoGrow(); await execute(value);
  });
  input.addEventListener("input", () => { autoGrow(); updateSuggestions(); });
  input.addEventListener("keydown", async (event) => {
    if (event.key === "Tab" && suggestions.length) { event.preventDefault(); acceptSuggestion(); return; }
    if (event.key === "Escape" && suggestions.length) { event.preventDefault(); hideSuggestions(); return; }
    if (event.ctrlKey && event.key.toLowerCase() === "c" && activeSession?.busy) { event.preventDefault(); await cancelExecution(); return; }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (activeSession?.busy || busy) return;
      const value = input.value; input.value = ""; hideSuggestions(); autoGrow(); await execute(value); return;
    }
    if (event.ctrlKey && event.key.toLowerCase() === "l") { event.preventDefault(); clear(); return; }
    if (!input.value.includes("\n") && event.key === "ArrowUp" && history.length) { event.preventDefault(); historyIndex = Math.max(0, historyIndex - 1); input.value = history[historyIndex] || ""; autoGrow(); }
    if (!input.value.includes("\n") && event.key === "ArrowDown" && history.length) { event.preventDefault(); historyIndex = Math.min(history.length, historyIndex + 1); input.value = history[historyIndex] || ""; autoGrow(); }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden && document.activeElement === input) close();
  });

  createSession();
  Promise.all([api("/api/terminal/health"), api("/api/modules")]).then(([payload, modules]) => {
    setCwd(payload.cwd);
    modulesCache = modules.modules || [];
    const tools = ["PowerShell", payload.gitAvailable && "Git", payload.pythonAvailable && "Python"].filter(Boolean);
    readyStatus = tools.length ? `pronto · ${tools.join(" + ")}` : "pronto";
    status.textContent = readyStatus;
  }).catch((error) => { status.textContent = "core indisponível"; appendBlackBoxError("Core indisponível", error?.stack || error?.message || String(error)); });
  const unsubscribeBlackBox = BlackBox.subscribe((event) => {
    if (!event || !["error", "warning"].includes(event.level)) return;
    const duplicateIndex = pendingTerminalErrors.findIndex((item) => (
      event.title === item.title
      && (!item.cwd || !event.path || event.path === item.cwd)
      && (!item.detail || event.detail?.includes(item.detail))
    ));
    if (duplicateIndex >= 0) pendingTerminalErrors.splice(duplicateIndex, 1);
    else appendBlackBoxError(event.title || "Erro na interface", event.detail || "");
    launcher?.classList.add("has-notification");
  });
  panel.addEventListener("pointerdown", () => launcher?.classList.remove("has-notification"));
  return Object.freeze({ open, close, clear, execute, newTab: createSession, element: panel });
}
