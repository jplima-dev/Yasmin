import { apiRequest } from "./origin.js";
const handlers = new Map();

async function api(path, options = {}) {
  return apiRequest(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
}

async function publish(moduleId) {
  const handler = handlers.get(moduleId);
  if (!handler?.exportData) throw new Error("O módulo não registrou uma função de exportação.");
  const data = await handler.exportData();
  return api(`/api/module-data/${encodeURIComponent(moduleId)}`, {
    method: "POST",
    body: JSON.stringify({ schemaVersion: handler.schemaVersion, data }),
  });
}

async function restore(moduleId) {
  const handler = handlers.get(moduleId);
  if (!handler?.importData) throw new Error("O módulo não registrou uma função de restauração.");
  const snapshot = await api(`/api/module-data/${encodeURIComponent(moduleId)}`);
  await handler.importData(snapshot.data, { schemaVersion: snapshot.schemaVersion });
  return snapshot;
}

function register({ moduleId, schemaVersion = 1, exportData, importData }) {
  if (!/^[a-z][a-z0-9-]{1,39}$/.test(moduleId || "")) throw new Error("ID de módulo inválido.");
  if (typeof exportData !== "function" || typeof importData !== "function") {
    throw new TypeError("Informe exportData e importData.");
  }
  handlers.set(moduleId, { schemaVersion, exportData, importData });
  return Object.freeze({
    publish: () => publish(moduleId),
    restore: () => restore(moduleId),
    unregister: () => handlers.delete(moduleId),
  });
}

export const ModuleData = Object.freeze({ register, publish, restore, list: () => api("/api/module-data") });
