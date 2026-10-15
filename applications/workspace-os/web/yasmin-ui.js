import { apiRequest } from "/core/origin.js";
import { deriveYasminVisual, visibleProcesses } from "/yasmin-state.js";

const ui = { messages: [], modules: [], busy: false, polling: false };

function localModule(module) {
  if (!module?.url || module.enabled === false || module.compatible === false || !module.installed) return false;
  if (!["static-web", "web-service"].includes(module.kind)) return false;
  if (module.kind === "web-service" && !module.reachable) return false;
  try {
    const url = new URL(module.url, location.origin);
    return url.origin === location.origin || (url.protocol === "http:" && ["127.0.0.1", "localhost"].includes(url.hostname));
  } catch { return false; }
}

export function updateYasminModules(modules) { ui.modules = modules; }

export function openInYasmin(module) {
  if (!localModule(module)) return false;
  const stage = document.querySelector("#yasmin-stage");
  const title = stage?.querySelector("#yasmin-stage-title");
  const link = stage?.querySelector("#yasmin-stage-link");
  const frame = stage?.querySelector("iframe");
  if (!stage || !title || !link || !frame) return false;
  const url = new URL(module.url, location.origin).href;
  title.textContent = module.name;
  link.href = url;
  frame.src = url;
  frame.title = module.name;
  stage.hidden = false;
  return true;
}

function addMessage(role, text) {
  ui.messages.push({ role, text: String(text) });
  if (ui.messages.length > 40) ui.messages.shift();
  const area = document.querySelector("#yasmin-messages");
  if (!area) return;
  const item = document.createElement("p");
  item.className = `yasmin-message ${role}`;
  const label = document.createElement("strong");
  label.textContent = role === "user" ? "Você" : "Yasmin";
  const content = document.createElement("span");
  content.textContent = String(text);
  item.append(label, content);
  area.append(item);
  area.scrollTop = area.scrollHeight;
}

function visual(state = {}) {
  const dock = document.querySelector("#yasmin-dock");
  const detail = document.querySelector("#yasmin-dock-detail");
  const processes = document.querySelector("#yasmin-dock-processes");
  if (!dock || !detail) return;
  const active = ["interpretando", "planejando", "executando"].includes(state.estado_agente);
  const current = ui.busy && !active
    ? { ok: true, estado_agente: "executando", tarefa_atual: "Interpretando seu pedido",
        processos: [{ descricao: "Interpretando seu pedido", status: "executando" }] }
    : state;
  const { mode, text } = deriveYasminVisual(current, ui.busy);
  dock.classList.toggle("is-working", mode === "working");
  dock.classList.toggle("is-speaking", mode === "speaking");
  dock.classList.toggle("is-listening", mode === "listening");
  dock.classList.toggle("is-offline", mode === "offline");
  detail.textContent = text;
  detail.title = text;
  dock.setAttribute("aria-label", `Yasmin: ${text}. Abrir conversa`);
  if (processes) {
    processes.replaceChildren();
    const recent = mode === "working" || mode === "speaking" ? visibleProcesses(current) : [];
    for (const item of recent) {
      const line = document.createElement("span");
      line.className = `yasmin-process yasmin-process-${item.status}`;
      line.textContent = item.descricao;
      processes.append(line);
    }
  }
}

async function pollStatus() {
  if (ui.polling) return;
  ui.polling = true;
  try { visual(await apiRequest("/api/yasmin/health")); }
  catch { visual({ ok: false }); }
  finally { ui.polling = false; }
}

export function mountYasminDock({ onModule }) {
  const dock = document.querySelector("#yasmin-dock");
  const panel = document.querySelector("#yasmin-panel");
  if (!dock || !panel) return;
  const toggle = () => {
    panel.hidden = !panel.hidden;
    dock.setAttribute("aria-expanded", String(!panel.hidden));
    if (!panel.hidden) panel.querySelector("#yasmin-command-input")?.focus();
  };
  dock.addEventListener("click", toggle);
  panel.querySelector("#yasmin-panel-close")?.addEventListener("click", toggle);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) toggle();
  });
  panel.querySelector("#yasmin-command-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (ui.busy) return;
    const input = panel.querySelector("#yasmin-command-input");
    const texto = input.value.trim();
    if (!texto) return;
    input.value = "";
    addMessage("user", texto);
    ui.busy = true;
    visual({ ok: true, estado_agente: "executando", tarefa_atual: "Interpretando seu pedido" });
    const botao = panel.querySelector("#yasmin-send");
    botao.disabled = true;
    try {
      const dados = await apiRequest("/api/yasmin/command", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto }),
      });
      addMessage("assistant", dados.resposta || "Não recebi uma resposta verificável para esse comando.");
      if (dados.aplicacao) {
        try {
          const catalogo = await apiRequest("/api/modules");
          updateYasminModules(catalogo.modules || []);
        } catch { /* O comando terminou; mantém o catálogo local. */ }
        const module = ui.modules.find((item) => item.id === dados.aplicacao);
        if (module) onModule(module);
      }
    } catch (error) {
      addMessage("assistant", error.erro || error.message || "Não consegui executar o comando.");
    } finally {
      ui.busy = false;
      botao.disabled = false;
      pollStatus();
    }
  });
  document.querySelector("#yasmin-close-stage")?.addEventListener("click", () => {
    const stage = document.querySelector("#yasmin-stage");
    stage.hidden = true;
    stage.querySelector("iframe").src = "about:blank";
  });
  pollStatus();
  window.setInterval(pollStatus, 500);
}
