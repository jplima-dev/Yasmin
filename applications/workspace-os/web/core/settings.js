import { Events } from "./events.js";
import { normalizeHex } from "./theme.js";
import { apiRequest, CORE_ORIGIN } from "./origin.js";

export const SETTINGS_DEFAULTS = Object.freeze({
  schema_version: 2, revision: 0, theme: "light", accent: "#ff5b3d",
  language: "pt-BR",
  density: "comfortable", font_size: "comfortable", reduce_motion: false,
  high_contrast: false, decorations: true, sidebar_collapsed: false,
  dashboard_show_stats: true, dashboard_show_health: true, dashboard_card_size: "comfortable",
  favorite_modules: ["organizer", "bridge", "photos"],
  disabled_modules: [], file_associations: {},
  keyboard_shortcuts: { search: "Ctrl+K", terminal: "Ctrl+`", dropzone: "Ctrl+Shift+O", activities: "Ctrl+Shift+N" },
  open_panel_on_start: false, auto_start_modules: ["organizer", "bridge", "drive2"], module_urls: {},
  module_configs: {
    bridge: { host: "0.0.0.0", port: 8876, public_url: "", discovery_port: 48765, max_chunk_mb: 4, data_dir: "", received_dir: "", tls_cert: "", tls_key: "" },
    drive2: { run_local: true, host: "127.0.0.1", port: 8000, storage_root: "data/files", database: "drive2.db", temp_root: "data/temp", trash_root: "data/trash", emails_root: "data/emails", attachments_root: "data/attachments", log_level: "INFO", max_upload_mb: 1024, scan_interval_seconds: 60, sync_interval_seconds: 15, sync_max_retries: 8, tailscale_only: true, auth_enabled: false, auth_username: "admin", auth_cookie_secure: false, auth_session_hours: 24, r2_enabled: false, r2_region: "auto", r2_prefix: "drive2", gmail_enabled: false, gmail_credentials_path: "config/gmail_credentials.json", gmail_token_path: "config/gmail_token.json", gmail_archive_after_days: 30, gmail_max_message_mb: 50, gmail_protect_starred: true, gmail_protect_important: true, gmail_trash_after_backup: false },
  },
});

const CACHE_KEY = "workspace.settings.cache.v2";
const CHANNEL_NAME = "workspace-os-settings";
const API_URL = `${CORE_ORIGIN}/api/settings`;
const listeners = new Set();
let current = { ...SETTINGS_DEFAULTS };
let initialized = false;
let channel;
let pollTimer;

function validated(changes) {
  const result = { ...changes };
  if ("accent" in result) result.accent = normalizeHex(result.accent);
  if ("theme" in result && !["light", "dark", "system"].includes(result.theme)) delete result.theme;
  if ("language" in result && !["pt-BR", "en"].includes(result.language)) delete result.language;
  if ("density" in result && !["compact", "comfortable", "spacious"].includes(result.density)) delete result.density;
  if ("font_size" in result && !["small", "comfortable", "large"].includes(result.font_size)) delete result.font_size;
  if ("dashboard_card_size" in result && !["compact", "comfortable", "wide"].includes(result.dashboard_card_size)) delete result.dashboard_card_size;
  for (const key of ["dashboard_show_stats", "dashboard_show_health"]) {
    if (key in result && typeof result[key] !== "boolean") delete result[key];
  }
  if ("favorite_modules" in result) {
    if (!Array.isArray(result.favorite_modules) || !result.favorite_modules.every((item) => typeof item === "string")) delete result.favorite_modules;
    else result.favorite_modules = [...new Set(result.favorite_modules)];
  }
  if ("disabled_modules" in result) {
    if (!Array.isArray(result.disabled_modules) || !result.disabled_modules.every((item) => typeof item === "string")) delete result.disabled_modules;
    else result.disabled_modules = [...new Set(result.disabled_modules)];
  }
  if ("file_associations" in result && (!result.file_associations || typeof result.file_associations !== "object" || Array.isArray(result.file_associations))) delete result.file_associations;
  if ("keyboard_shortcuts" in result && (!result.keyboard_shortcuts || typeof result.keyboard_shortcuts !== "object" || Array.isArray(result.keyboard_shortcuts))) delete result.keyboard_shortcuts;
  return result;
}

function cache(settings) {
  try { localStorage.setItem(CACHE_KEY, JSON.stringify(settings)); } catch { /* armazenamento opcional */ }
}

function notify(settings, source) {
  current = { ...current, ...validated(settings) };
  cache(current);
  for (const listener of listeners) listener({ ...current }, source);
  Events.emit("settings:changed", { settings: { ...current }, source });
}

function broadcast(settings) {
  channel?.postMessage({ type: "settings-update", settings });
}

async function request(path = API_URL, options = {}) {
  return apiRequest(path, { headers: { "Content-Type": "application/json" }, ...options });
}

async function refresh() {
  const remote = await request();
  if (!initialized || Number(remote.revision || 0) !== Number(current.revision || 0)) notify(remote, "remote");
  return { ...current };
}

async function init() {
  if (initialized) return { ...current };
  initialized = true;
  try {
    const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || "null");
    if (cached) notify(cached, "cache");
  } catch { /* cache inválido é ignorado */ }
  if ("BroadcastChannel" in globalThis) {
    channel = new BroadcastChannel(CHANNEL_NAME);
    channel.addEventListener("message", (event) => {
      if (event.data?.type === "settings-update") notify(event.data.settings, "broadcast");
    });
  }
  addEventListener("storage", (event) => {
    if (event.key !== CACHE_KEY || !event.newValue) return;
    try { notify(JSON.parse(event.newValue), "storage"); } catch { /* valor externo inválido */ }
  });
  try { await refresh(); } catch (error) { Events.emit("settings:error", { error }); }
  pollTimer ||= setInterval(() => refresh().catch((error) => Events.emit("settings:error", { error })), 1200);
  return { ...current };
}

async function setMany(changes) {
  const previous = { ...current };
  const next = { ...current, ...validated(changes), revision: Number(current.revision || 0) + 1 };
  notify(next, "local");
  broadcast(next);
  try {
    const saved = await request(API_URL, { method: "POST", body: JSON.stringify(changes) });
    notify(saved, "saved");
    broadcast(saved);
    return { ...saved };
  } catch (error) {
    notify(previous, "rollback");
    broadcast(previous);
    Events.emit("settings:error", { error });
    throw error;
  }
}

export const Settings = Object.freeze({
  init,
  refresh,
  get(key) { return key ? current[key] : { ...current }; },
  set(key, value) { return setMany({ [key]: value }); },
  setMany,
  subscribe(listener, { immediate = true } = {}) {
    listeners.add(listener);
    if (immediate) listener({ ...current }, "subscribe");
    return () => listeners.delete(listener);
  },
  stop() { if (pollTimer) clearInterval(pollTimer); pollTimer = undefined; channel?.close(); channel = undefined; },
});
