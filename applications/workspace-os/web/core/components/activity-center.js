import { Activity } from "../activity.js";
import { Clipboard } from "../clipboard.js";
import { BlackBox } from "../blackbox.js";
import { coreUrl } from "../origin.js";

const STYLE_URL = coreUrl("/core/components/activity-center.css");

function ensureStyles() {
  if (document.querySelector(`link[href="${STYLE_URL}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_URL;
  document.head.append(link);
}

function formatDate(value) {
  try { return new Date(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }); }
  catch { return ""; }
}

export function mountActivityCenter({ target = document.body } = {}) {
  if (document.querySelector(".workspace-activity-host")) return null;
  ensureStyles();
  const host = document.createElement("div");
  host.className = "workspace-activity-host";
  host.innerHTML = `
    <button class="workspace-activity-launcher" type="button" aria-label="Abrir Central do Workspace" title="Central do Workspace" aria-expanded="false">♢</button>
    <section class="workspace-activity-panel" aria-label="Central de atividades" hidden>
      <header><div><strong>Central do Workspace</strong><span>Atividades e área de transferência interna</span></div><button type="button" data-activity-close aria-label="Fechar">×</button></header>
      <nav class="workspace-center-tabs" aria-label="Conteúdo da central"><button type="button" class="active" data-center-tab="activity">Atividades</button><button type="button" data-center-tab="clipboard">Clipboard</button><button type="button" data-center-tab="blackbox">Caixa-preta</button></nav>
      <section data-center-view="activity">
        <div class="workspace-activity-actions"><button type="button" data-activity-read>Ler todas</button><button type="button" data-activity-clear>Limpar histórico</button></div>
        <div class="workspace-activity-list" role="list"></div>
      </section>
      <section data-center-view="clipboard" hidden>
        <form class="workspace-clipboard-form"><textarea rows="2" maxlength="262144" placeholder="Cole ou escreva algo para usar em outros módulos" aria-label="Novo texto do clipboard interno"></textarea><button type="submit">Adicionar</button></form>
        <div class="workspace-clipboard-list" role="list"></div>
      </section>
      <section data-center-view="blackbox" hidden>
        <div class="workspace-activity-actions"><button type="button" data-blackbox-clear>Limpar eventos</button></div>
        <div class="workspace-blackbox-list" role="list"></div>
      </section>
    </section>`;
  target.append(host);

  const launcher = host.querySelector(".workspace-activity-launcher");
  const panel = host.querySelector(".workspace-activity-panel");
  const listRoot = host.querySelector(".workspace-activity-list");
  const clipboardRoot = host.querySelector(".workspace-clipboard-list");
  const clipboardForm = host.querySelector(".workspace-clipboard-form");
  const blackboxRoot = host.querySelector(".workspace-blackbox-list");

  async function refresh() {
    try {
      const items = await Activity.list();
      listRoot.replaceChildren();
      if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "workspace-activity-empty";
        empty.textContent = "Nenhuma atividade registrada ainda.";
        listRoot.append(empty);
        return;
      }
      for (const item of items.slice(0, 80)) {
        const row = document.createElement("article");
        row.className = `workspace-activity-item level-${item.level}${item.read ? " is-read" : ""}`;
        row.setAttribute("role", "listitem");
        const mark = document.createElement("span"); mark.className = "workspace-activity-mark"; mark.textContent = item.kind === "export" ? "⇩" : item.kind === "module" ? "▦" : item.level === "error" ? "!" : "•";
        const copy = document.createElement("span"); copy.className = "workspace-activity-copy";
        const title = document.createElement("strong"); title.textContent = item.title;
        const detail = document.createElement("small"); detail.textContent = item.detail || formatDate(item.createdAt);
        const time = document.createElement("time"); time.dateTime = item.createdAt; time.textContent = formatDate(item.createdAt);
        copy.append(title, detail); row.append(mark, copy, time);
        const actions = document.createElement("span"); actions.className = "workspace-activity-inline-actions";
        const available = [...(item.actions || [])];
        if (item.url) available.unshift({ label: "Abrir", url: item.url });
        for (const action of available.slice(0, 3)) {
          const link = document.createElement("a"); link.href = action.url; link.textContent = action.label; actions.append(link);
        }
        const dismiss = document.createElement("button"); dismiss.type = "button"; dismiss.textContent = "Descartar";
        dismiss.addEventListener("click", async () => { await Activity.remove(item.id); await refresh(); });
        actions.append(dismiss); row.append(actions); listRoot.append(row);
      }
    } catch (error) {
      listRoot.textContent = `Não foi possível carregar as atividades: ${error.message}`;
    }
  }

  async function refreshClipboard() {
    try {
      const items = await Clipboard.list();
      clipboardRoot.replaceChildren();
      if (!items.length) {
        const empty = document.createElement("div"); empty.className = "workspace-activity-empty"; empty.textContent = "O clipboard interno está vazio."; clipboardRoot.append(empty); return;
      }
      for (const item of items) {
        const row = document.createElement("article"); row.className = `workspace-clipboard-item${item.pinned ? " is-pinned" : ""}`; row.setAttribute("role", "listitem");
        const text = document.createElement("pre"); text.textContent = item.text;
        const meta = document.createElement("small"); meta.textContent = `${item.label || item.source || "Workspace"} · ${formatDate(item.createdAt)}`;
        const actions = document.createElement("div"); actions.className = "workspace-clipboard-actions";
        const copy = document.createElement("button"); copy.type = "button"; copy.textContent = "Copiar"; copy.addEventListener("click", async () => { await Clipboard.copy(item); copy.textContent = "Copiado"; setTimeout(() => { copy.textContent = "Copiar"; }, 1200); });
        const pin = document.createElement("button"); pin.type = "button"; pin.textContent = item.pinned ? "Desafixar" : "Fixar"; pin.addEventListener("click", async () => { await Clipboard.pin(item.id, !item.pinned); await refreshClipboard(); });
        const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "Remover"; remove.addEventListener("click", async () => { await Clipboard.remove(item.id); await refreshClipboard(); });
        actions.append(copy, pin, remove); row.append(text, meta, actions); clipboardRoot.append(row);
      }
    } catch (error) { clipboardRoot.textContent = `Não foi possível carregar o clipboard: ${error.message}`; }
  }

  async function refreshBlackBox() {
    try {
      const items = await BlackBox.list();
      blackboxRoot.replaceChildren();
      if (!items.length) { const empty = document.createElement("div"); empty.className = "workspace-activity-empty"; empty.textContent = "Nenhum evento técnico registrado."; blackboxRoot.append(empty); return; }
      for (const item of items.slice(0, 100)) {
        const row = document.createElement("article"); row.className = `workspace-blackbox-item level-${item.level}`; row.setAttribute("role", "listitem");
        const heading = document.createElement("strong"); heading.textContent = `[${item.kind}] ${item.title}`;
        const detail = document.createElement("pre"); detail.textContent = item.detail || item.path || "Sem detalhes";
        const meta = document.createElement("small"); meta.textContent = `${item.moduleId || "Core"} · ${formatDate(item.createdAt)}`;
        row.append(heading, detail, meta); blackboxRoot.append(row);
      }
    } catch (error) { blackboxRoot.textContent = `Não foi possível carregar a caixa-preta: ${error.message}`; }
  }

  function showView(name) {
    host.querySelectorAll("[data-center-tab]").forEach((button) => button.classList.toggle("active", button.dataset.centerTab === name));
    host.querySelectorAll("[data-center-view]").forEach((view) => { view.hidden = view.dataset.centerView !== name; });
    if (name === "clipboard") refreshClipboard(); else if (name === "blackbox") refreshBlackBox(); else refresh();
  }

  function open(view = "activity") { panel.hidden = false; launcher.setAttribute("aria-expanded", "true"); launcher.blur(); showView(view); }
  function close() { panel.hidden = true; launcher.setAttribute("aria-expanded", "false"); launcher.blur(); }
  launcher.addEventListener("click", () => panel.hidden ? open() : close());
  host.querySelector("[data-activity-close]").addEventListener("click", close);
  host.querySelector("[data-activity-read]").addEventListener("click", async () => { await Activity.markAllRead(); await refresh(); });
  host.querySelector("[data-activity-clear]").addEventListener("click", async () => { await Activity.clear(); await refresh(); });
  host.querySelector("[data-blackbox-clear]").addEventListener("click", async () => { await BlackBox.clear(); await refreshBlackBox(); });
  host.querySelectorAll("[data-center-tab]").forEach((button) => button.addEventListener("click", () => showView(button.dataset.centerTab)));
  clipboardForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = clipboardForm.querySelector("textarea");
    if (!input.value.trim()) return;
    await Clipboard.add(input.value, { source: document.title });
    input.value = "";
    await refreshClipboard();
  });
  document.addEventListener("pointerdown", (event) => { if (!panel.hidden && !panel.contains(event.target) && !launcher.contains(event.target)) close(); });
  const unsubscribe = Activity.subscribe(refresh);
  refresh();
  return Object.freeze({ open, close, refresh, refreshClipboard, refreshBlackBox, destroy() { unsubscribe(); host.remove(); } });
}
