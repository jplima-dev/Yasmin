import { apiRequest } from "./origin.js";

async function request(path = "/api/clipboard", options = {}) {
  return apiRequest(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
}

export const Clipboard = Object.freeze({
  async list() { return (await request()).items || []; },
  add(text, options = {}) {
    return request("/api/clipboard", { method: "POST", body: JSON.stringify({ text, ...options }) });
  },
  pin(id, pinned = true) {
    return request(`/api/clipboard/${encodeURIComponent(id)}/pin`, { method: "POST", body: JSON.stringify({ pinned }) });
  },
  remove(id) { return request(`/api/clipboard/${encodeURIComponent(id)}`, { method: "DELETE" }); },
  async copy(itemOrText) {
    const text = typeof itemOrText === "string" ? itemOrText : itemOrText?.text || "";
    await navigator.clipboard.writeText(text);
    return text;
  },
});
