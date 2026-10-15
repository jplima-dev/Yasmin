import { apiRequest } from "./origin.js";
const listeners = new Set();
let timer;
let newest = "";
let moduleId = "";

async function request(path = "/api/blackbox", options = {}) {
  return apiRequest(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
}

async function report(entry) {
  return request("/api/blackbox", { method: "POST", keepalive: true, body: JSON.stringify({ moduleId, ...entry }) });
}

async function poll({ initial = false } = {}) {
  try {
    const items = (await request()).items || [];
    const fresh = newest ? items.filter((item) => item.createdAt > newest) : [];
    if (items[0]?.createdAt) newest = items[0].createdAt;
    if (!initial) for (const item of fresh.reverse()) for (const listener of listeners) listener(item);
  } catch { /* o Core pode estar reiniciando */ }
}

function start(id = "") {
  moduleId = id || moduleId;
  if (timer) return;
  addEventListener("error", (event) => report({
    kind: "error", level: "error", title: event.message || "Erro na interface",
    detail: `${event.filename || location.href}:${event.lineno || 0}:${event.colno || 0}`,
  }).catch(() => {}));
  addEventListener("unhandledrejection", (event) => report({
    kind: "error", level: "error", title: "Promessa rejeitada na interface",
    detail: String(event.reason?.stack || event.reason || "Erro sem detalhes"),
  }).catch(() => {}));
  poll({ initial: true });
  timer = setInterval(() => poll(), 3000);
}

export const BlackBox = Object.freeze({
  start, report, list: async () => (await request()).items || [], clear: () => request("/api/blackbox", { method: "DELETE" }),
  subscribe(listener) { listeners.add(listener); start(moduleId); return () => listeners.delete(listener); },
});
