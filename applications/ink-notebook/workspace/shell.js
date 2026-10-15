const frame = document.querySelector("#notebook-frame");
const status = document.querySelector("#notebook-status");
const variableSources = {
  "--bg": "--bg", "--surface": "--surface", "--panel": "--panel", "--panel2": "--panel-2",
  "--border": "--border", "--text": "--text", "--muted": "--muted", "--accent": "--accent",
  "--accent-soft": "--accent-soft", "--danger": "--red", "--ok": "--green", "--warn": "--amber",
  "--mark": "--accent-soft", "--shadow": "--ws-shadow-1",
};

let serviceOrigin = "";

function validLoopbackUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname) ? url.origin : "";
  } catch {
    return "";
  }
}

function workspaceTheme() {
  const computed = getComputedStyle(document.documentElement);
  return {
    type: "workspace:notebook-theme",
    theme: document.documentElement.dataset.theme === "dark" ? "dark" : "light",
    variables: Object.fromEntries(Object.entries(variableSources).map(([name, source]) => [name, computed.getPropertyValue(source).trim()])),
  };
}

function sendTheme() {
  if (frame.contentWindow && serviceOrigin) frame.contentWindow.postMessage(workspaceTheme(), serviceOrigin);
}

async function connect() {
  try {
    const response = await fetch("/api/modules");
    if (!response.ok) throw new Error(`Resposta ${response.status}`);
    const payload = await response.json();
    const module = (payload.modules || []).find((item) => item.id === "notebook");
    serviceOrigin = validLoopbackUrl(module?.serviceUrl);
    if (!serviceOrigin) throw new Error("O endereço local do serviço não foi configurado.");
    frame.src = `${serviceOrigin}/`;
    frame.hidden = false;
    status.hidden = true;
  } catch (error) {
    status.textContent = `Não foi possível abrir o Ink Notebook: ${error.message}`;
  }
}

window.addEventListener("message", (event) => {
  if (event.origin === serviceOrigin && event.data?.type === "workspace:notebook-ready") sendTheme();
});
frame.addEventListener("load", sendTheme);

const waitForSettings = window.setInterval(() => {
  if (!globalThis.Mega?.settings) return;
  window.clearInterval(waitForSettings);
  globalThis.Mega.settings.subscribe(sendTheme, { immediate: true });
}, 25);
window.setTimeout(() => window.clearInterval(waitForSettings), 5_000);

connect();
