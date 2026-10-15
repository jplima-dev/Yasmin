import { Activity } from "./activity.js";
import { SETTINGS_DEFAULTS, Settings } from "./settings.js";
import { apiRequest, authorizedFetch } from "./origin.js";

const FORMAT = "ink-workspace-backup";
const VERSION = 1;
const SETTINGS_KEYS = Object.keys(SETTINGS_DEFAULTS).filter((key) => !["schema_version", "revision"].includes(key));

function workspaceBrowserData() {
  const data = {};
  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index);
    if (key?.startsWith("workspace.") && key !== "workspace.settings.cache.v2") data[key] = localStorage.getItem(key);
  }
  return data;
}

async function api(path, options = {}) {
  return apiRequest(path, options);
}

export async function createWorkspaceBackup() {
  const [settings, modules, activity, dropzone, presets, clipboard] = await Promise.all([
    api("/api/settings"), api("/api/modules"), api("/api/activity"), api("/api/dropzone/history"), api("/api/presets"), api("/api/clipboard"),
  ]);
  return {
    format: FORMAT,
    version: VERSION,
    createdAt: new Date().toISOString(),
    workspaceVersion: (await api("/api/health")).version,
    settings: Object.fromEntries(SETTINGS_KEYS.map((key) => [key, settings[key]])),
    browserData: workspaceBrowserData(),
    activity: (activity.items || []).slice(0, 100),
    presets: presets.items || [],
    clipboard: (clipboard.items || []).filter((item) => item.pinned).map(({ text, label, source, pinned }) => ({ text, label, source, pinned })),
    dropzone: (dropzone.items || []).map(({ id, name, type, size, kind, createdAt }) => ({ id, name, type, size, kind, createdAt })),
    modules: (modules.modules || []).map(({ id, name, kind }) => ({ id, name, kind })),
  };
}

export async function downloadWorkspaceBackup() {
  const backup = await createWorkspaceBackup();
  const stamp = backup.createdAt.slice(0, 10);
  const url = URL.createObjectURL(new Blob([JSON.stringify(backup, null, 2)], { type: "application/json" }));
  const anchor = Object.assign(document.createElement("a"), { href: url, download: `ink-workspace-backup-${stamp}.json` });
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  Activity.record({ kind: "backup", level: "success", title: "Backup do Workspace criado", detail: anchor.download }).catch(() => {});
  return backup;
}

export async function restoreWorkspaceBackup(file) {
  if (!file) throw new Error("Escolha um arquivo de backup.");
  if (file.size > 10 * 1024 * 1024) throw new Error("O backup excede o limite de 10 MB.");
  let backup;
  try { backup = JSON.parse(await file.text()); }
  catch { throw new Error("O arquivo escolhido não contém JSON válido."); }
  if (backup?.format !== FORMAT || backup?.version !== VERSION || !backup.settings || typeof backup.settings !== "object") {
    throw new Error("Este arquivo não é um backup compatível do Ink Workspace.");
  }
  const settings = Object.fromEntries(SETTINGS_KEYS.filter((key) => key in backup.settings).map((key) => [key, backup.settings[key]]));
  await Settings.setMany(settings);
  if (backup.browserData && typeof backup.browserData === "object") {
    for (const [key, value] of Object.entries(backup.browserData)) {
      if (key.startsWith("workspace.") && key !== "workspace.settings.cache.v2" && typeof value === "string") localStorage.setItem(key, value);
    }
  }
  if (Array.isArray(backup.presets)) {
    for (const preset of backup.presets.slice(0, 200)) {
      const { id: _ignored, createdAt: _created, updatedAt: _updated, ...safePreset } = preset;
      await api("/api/presets", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(safePreset) });
    }
  }
  if (Array.isArray(backup.clipboard)) {
    for (const item of backup.clipboard.slice(0, 100)) {
      await api("/api/clipboard", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...item, pinned: true }) });
    }
  }
  await Activity.record({ kind: "backup", level: "success", title: "Backup do Workspace restaurado", detail: file.name });
  return backup;
}

export async function downloadPortableArchive(sections = ["settings", "presets", "clipboard", "activity", "files", "modules"]) {
  const response = await authorizedFetch(`/api/portable/export?sections=${encodeURIComponent(sections.join(","))}`);
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || `Falha ${response.status}`);
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] || `ink-workspace-portable-${new Date().toISOString().slice(0, 10)}.zip`;
  const url = URL.createObjectURL(blob);
  Object.assign(document.createElement("a"), { href: url, download: filename }).click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  Activity.record({ kind: "backup", level: "success", title: "Pacote portátil criado", detail: filename }).catch(() => {});
  return { filename, size: blob.size };
}

export async function inspectPortableArchive(file) {
  if (!file || file.size > 512 * 1024 * 1024) throw new Error("Escolha um pacote portátil de até 512 MiB.");
  const response = await authorizedFetch("/api/portable/inspect", { method: "POST", headers: { "Content-Type": "application/zip" }, body: file });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Falha ${response.status}`);
  return payload;
}

export async function restorePortableArchive(file, sections = []) {
  const response = await authorizedFetch(`/api/portable/import?sections=${encodeURIComponent(sections.join(","))}`, {
    method: "POST", headers: { "Content-Type": "application/zip" }, body: file,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Falha ${response.status}`);
  Activity.record({ kind: "backup", level: "success", title: "Pacote portátil restaurado", detail: file.name }).catch(() => {});
  return payload;
}
