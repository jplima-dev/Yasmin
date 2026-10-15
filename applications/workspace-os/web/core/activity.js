import { apiRequest } from "./origin.js";
const listeners = new Set();

async function request(path = "/api/activity", options = {}) {
  return apiRequest(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
}

function notify(item = null) {
  for (const listener of listeners) listener(item);
  document.dispatchEvent(new CustomEvent("workspace:activity", { detail: item }));
}

async function list() {
  return (await request()).items || [];
}

async function record(entry) {
  const item = await request("/api/activity", {
    method: "POST",
    keepalive: true,
    body: JSON.stringify(entry),
  });
  notify(item);
  return item;
}

export const Activity = Object.freeze({
  list,
  record,
  async markAllRead() {
    const result = await request("/api/activity/read-all", { method: "POST", body: "{}" });
    notify();
    return result;
  },
  async clear() {
    const result = await request("/api/activity", { method: "DELETE" });
    notify();
    return result;
  },
  async remove(id) {
    const result = await request(`/api/activity/${encodeURIComponent(id)}`, { method: "DELETE" });
    notify();
    return result;
  },
  subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
});

export function observeExports({ moduleId = "" } = {}) {
  document.addEventListener("click", (event) => {
    const anchor = event.target.closest?.("a[download]");
    if (!anchor) return;
    const name = anchor.download || "arquivo exportado";
    Activity.record({
      kind: "export",
      level: "success",
      title: `Exportação: ${name}`,
      detail: document.title,
      moduleId,
    }).catch(() => {});
  }, true);
}
