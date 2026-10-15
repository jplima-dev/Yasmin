import { CORE_ORIGIN, coreUrl } from "./origin.js";

const MESSAGE_TYPE = "workspace:split-view";
const PANE_PARAMETER = "workspacePane";
const STYLE_URL = new URL("./split-view.css", import.meta.url).href;
const pendingRequests = new Map();
let requestSequence = 0;

const state = {
  shell: null,
  divider: null,
  chooser: null,
  chooserText: null,
  chooserButtons: [],
  panes: [],
  ratio: 50,
};

function ensureStyles() {
  if (document.querySelector('[data-workspace-split-style]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_URL;
  link.dataset.workspaceSplitStyle = "true";
  document.head.append(link);
}

function paneUrl(value, paneId) {
  const url = new URL(value, location.href);
  url.searchParams.set(PANE_PARAMETER, paneId);
  return url.href;
}

function cleanPaneUrl(value) {
  const url = new URL(value, location.href);
  url.searchParams.delete(PANE_PARAMETER);
  return url.href;
}

function currentFrameUrl(pane) {
  try {
    return pane.frame.contentWindow.location.href;
  } catch {
    return pane.frame.src;
  }
}

function currentFrameTitle(pane, fallback) {
  try {
    return pane.frame.contentDocument?.title || fallback;
  } catch {
    return fallback;
  }
}

function makeButton(label, className = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  return button;
}

function createPane(url, paneId, label) {
  const pane = document.createElement("section");
  pane.className = "workspace-split-pane";
  pane.dataset.splitPane = paneId;
  const badge = document.createElement("span");
  badge.className = "workspace-split-pane-badge";
  badge.textContent = label;
  const frame = document.createElement("iframe");
  frame.className = "workspace-split-frame";
  frame.name = `workspace-split-${paneId}`;
  frame.title = label;
  frame.src = paneUrl(url, paneId);
  frame.setAttribute("allow", "clipboard-read; clipboard-write");
  frame.addEventListener("load", () => {
    const title = currentFrameTitle({ frame }, label);
    frame.title = title;
    badge.textContent = title;
    window.setTimeout(() => badge.classList.add("is-quiet"), 1600);
  });
  pane.append(frame, badge);
  return { id: paneId, element: pane, frame, badge };
}

function installDivider(shell) {
  const divider = makeButton("⋮", "workspace-split-divider");
  divider.setAttribute("role", "separator");
  divider.setAttribute("aria-label", "Redimensionar telas");
  divider.setAttribute("aria-orientation", "vertical");
  divider.setAttribute("aria-valuemin", "20");
  divider.setAttribute("aria-valuemax", "80");
  divider.setAttribute("aria-valuenow", "50");
  const update = (clientX) => {
    const bounds = shell.getBoundingClientRect();
    const next = Math.max(20, Math.min(80, ((clientX - bounds.left) / bounds.width) * 100));
    state.ratio = Math.round(next * 10) / 10;
    shell.style.setProperty("--workspace-split-ratio", `${state.ratio}%`);
    divider.setAttribute("aria-valuenow", String(Math.round(state.ratio)));
  };
  divider.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    divider.setPointerCapture(event.pointerId);
    shell.classList.add("is-resizing");
  });
  divider.addEventListener("pointermove", (event) => {
    if (!divider.hasPointerCapture(event.pointerId)) return;
    update(event.clientX);
  });
  const finishResize = (event) => {
    if (divider.hasPointerCapture(event.pointerId)) divider.releasePointerCapture(event.pointerId);
    shell.classList.remove("is-resizing");
  };
  divider.addEventListener("pointerup", finishResize);
  divider.addEventListener("pointercancel", finishResize);
  divider.addEventListener("keydown", (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    if (event.key === "Home") state.ratio = 20;
    else if (event.key === "End") state.ratio = 80;
    else state.ratio = Math.max(20, Math.min(80, state.ratio + (event.key === "ArrowLeft" ? -2 : 2)));
    shell.style.setProperty("--workspace-split-ratio", `${state.ratio}%`);
    divider.setAttribute("aria-valuenow", String(Math.round(state.ratio)));
  });
  state.divider = divider;
  return divider;
}

function choosePane(index) {
  const selected = state.panes[index];
  if (!selected) return;
  const discarded = state.panes.filter((_, paneIndex) => paneIndex !== index);
  discarded.forEach((pane) => pane.element.remove());
  state.panes = [selected];
  state.divider.hidden = true;
  state.shell.classList.remove("is-divided");
  state.shell.classList.add("is-single");
  state.chooser.hidden = true;
  selected.badge.classList.add("is-quiet");
  selected.element.dataset.splitPane = "single";
  selected.element.style.gridColumn = "1 / -1";
  try {
    history.replaceState(history.state, "", cleanPaneUrl(currentFrameUrl(selected)));
  } catch { /* a instância selecionada continua mesmo sem sincronizar a URL */ }
  selected.frame.focus();
}

function installChooser(shell) {
  const backdrop = document.createElement("div");
  backdrop.className = "workspace-split-chooser";
  backdrop.hidden = true;
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");
  backdrop.setAttribute("aria-labelledby", "workspace-split-chooser-title");
  const card = document.createElement("div");
  card.className = "workspace-split-chooser-card";
  const eyebrow = document.createElement("span");
  eyebrow.textContent = "SUBDIVISÃO";
  const title = document.createElement("h2");
  title.id = "workspace-split-chooser-title";
  title.textContent = "Qual tela deve continuar?";
  const description = document.createElement("p");
  description.textContent = "A outra tela será fechada. A escolhida continua exatamente no estado atual.";
  const actions = document.createElement("div");
  actions.className = "workspace-split-chooser-actions";
  const keepFirst = makeButton("Continuar com a tela 1", "is-primary");
  const keepSecond = makeButton("Continuar com a tela 2", "is-primary");
  const cancel = makeButton("Cancelar");
  keepFirst.addEventListener("click", () => choosePane(0));
  keepSecond.addEventListener("click", () => choosePane(1));
  cancel.addEventListener("click", () => { backdrop.hidden = true; });
  actions.append(keepFirst, keepSecond, cancel);
  card.append(eyebrow, title, description, actions);
  backdrop.append(card);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) backdrop.hidden = true;
  });
  backdrop.addEventListener("keydown", (event) => {
    if (event.key === "Escape") backdrop.hidden = true;
  });
  shell.append(backdrop);
  state.chooser = backdrop;
  state.chooserText = description;
  state.chooserButtons = [keepFirst, keepSecond];
}

function renderDivided() {
  state.shell.classList.remove("is-single");
  state.shell.classList.add("is-divided");
  state.divider.hidden = false;
  state.panes[0].element.style.gridColumn = "1";
  state.divider.style.gridColumn = "2";
  state.panes[1].element.style.gridColumn = "3";
  for (const element of [state.panes[0].element, state.divider, state.panes[1].element, state.chooser]) {
    if (element.parentNode !== state.shell) state.shell.append(element);
  }
}

function createShell() {
  ensureStyles();
  const shell = document.createElement("section");
  shell.className = "workspace-split-shell";
  shell.setAttribute("aria-label", "Workspace subdividido");
  shell.style.setProperty("--workspace-split-ratio", `${state.ratio}%`);
  state.shell = shell;
  installDivider(shell);
  installChooser(shell);
  document.body.classList.add("workspace-split-owner");
  document.body.append(shell);
  return shell;
}

function subdivideTop() {
  if (state.panes.length >= 2) {
    return { ok: false, message: "A tela já está subdividida." };
  }
  if (!state.shell) {
    const source = cleanPaneUrl(location.href);
    const splitUrl = new URL(coreUrl("/split.html"));
    splitUrl.searchParams.set("source", source);
    location.assign(splitUrl.href);
    return { ok: true, message: "Abrindo duas instâncias independentes desta tela." };
  } else {
    const source = cleanPaneUrl(currentFrameUrl(state.panes[0]));
    const paneId = state.panes[0].id === "one" ? "two" : "one";
    state.panes.push(createPane(source, paneId, "Tela 2"));
  }
  renderDivided();
  return { ok: true, message: "Tela subdividida em duas instâncias independentes." };
}

function unSubdivideTop() {
  if (state.panes.length < 2) {
    return { ok: false, message: "A tela não está subdividida." };
  }
  const names = state.panes.map((pane, index) => currentFrameTitle(pane, `Tela ${index + 1}`));
  state.chooserButtons[0].textContent = `Continuar com: ${names[0]}`;
  state.chooserButtons[1].textContent = `Continuar com: ${names[1]}`;
  state.chooserText.textContent = "A outra tela será fechada. A escolhida continua exatamente no estado atual.";
  state.chooser.hidden = false;
  state.chooserButtons[0].focus();
  return { ok: true, message: "Escolha na janela qual tela deve continuar." };
}

function parentRequest(action) {
  const requestId = `split-${Date.now()}-${++requestSequence}`;
  return new Promise((resolve) => {
    const timeout = window.setTimeout(() => {
      pendingRequests.delete(requestId);
      resolve({ ok: false, message: "A tela principal não respondeu ao comando." });
    }, 2500);
    pendingRequests.set(requestId, (result) => {
      window.clearTimeout(timeout);
      resolve(result);
    });
    window.parent.postMessage({ type: MESSAGE_TYPE, action, requestId }, CORE_ORIGIN);
  });
}

function sourceIsManaged(source) {
  return state.panes.some((pane) => pane.frame.contentWindow === source);
}

window.addEventListener("message", (event) => {
  if (event.origin !== CORE_ORIGIN || event.data?.type !== MESSAGE_TYPE) return;
  if (event.data.action === "result") {
    const resolve = pendingRequests.get(event.data.requestId);
    if (!resolve) return;
    pendingRequests.delete(event.data.requestId);
    resolve(event.data.result);
    return;
  }
  if (window.top !== window || !sourceIsManaged(event.source)) return;
  const result = event.data.action === "subdivide" ? subdivideTop() : unSubdivideTop();
  event.source?.postMessage(
    { type: MESSAGE_TYPE, action: "result", requestId: event.data.requestId, result },
    event.origin,
  );
});

export function subdivideView() {
  return window.top === window ? Promise.resolve(subdivideTop()) : parentRequest("subdivide");
}

export function unSubdivideView() {
  return window.top === window ? Promise.resolve(unSubdivideTop()) : parentRequest("unsubidivide");
}

export function splitViewStatus() {
  if (window.top !== window) return { embedded: true, pane: new URL(location.href).searchParams.get(PANE_PARAMETER) || "" };
  return { embedded: false, panes: state.panes.length, divided: state.panes.length === 2 };
}

export function initializeSplitView(sourceUrl) {
  if (window.top !== window || state.shell) return false;
  const source = new URL(sourceUrl, CORE_ORIGIN);
  if (source.origin !== CORE_ORIGIN || source.pathname === "/split.html") return false;
  createShell();
  state.panes = [
    createPane(cleanPaneUrl(source.href), "one", "Tela 1"),
    createPane(cleanPaneUrl(source.href), "two", "Tela 2"),
  ];
  renderDivided();
  return true;
}
