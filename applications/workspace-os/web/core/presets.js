import { Activity } from "./activity.js";
import { apiRequest } from "./origin.js";

async function request(path = "/api/presets", options = {}) {
  return apiRequest(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
}

export const Presets = Object.freeze({
  async list({ moduleId = "" } = {}) {
    const items = (await request()).items || [];
    return moduleId ? items.filter((item) => !item.moduleIds?.length || item.moduleIds.includes(moduleId)) : items;
  },
  async save(preset) {
    const saved = await request("/api/presets", { method: "POST", body: JSON.stringify(preset) });
    Activity.record({ kind: "system", level: "success", title: `Preset salvo: ${saved.name}`, detail: (saved.moduleIds || []).join(", ") }).catch(() => {});
    return saved;
  },
  async remove(id) {
    return request(`/api/presets/${encodeURIComponent(id)}`, { method: "DELETE" });
  },
});
