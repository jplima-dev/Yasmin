import { Events } from "./events.js";
import { Settings } from "./settings.js";
import { createNamespace } from "./storage.js";
import { applyGlobalTheme, derivePalette } from "./theme.js";
import { confirmDialog } from "./components/modal.js";
import { toast } from "./components/toast.js";
import { observeButtonTypes } from "./dom.js";
import { mountTerminal } from "./components/terminal.js";
import { mountActivityCenter } from "./components/activity-center.js";
import { deliverIncomingDrop, getDropFolder, getIncomingDrop, mountUniversalDropzone, sendDropFile, storeDropFile } from "./dropzone.js";
import { Activity, observeExports } from "./activity.js";
import { Presets } from "./presets.js";
import { Clipboard } from "./clipboard.js";
import { ModuleData } from "./module-data.js";
import { mountShortcuts } from "./shortcuts.js";
import { I18n } from "./i18n.js";
import { BlackBox } from "./blackbox.js";
import { CORE_ORIGIN, coreUrl } from "./origin.js";

const designStylesheet = coreUrl("/design-system/workspace-ui.css");
if (!document.querySelector(`link[href="${designStylesheet}"]`)) {
  const design = document.createElement("link");
  design.rel = "stylesheet";
  design.href = designStylesheet;
  design.dataset.workspaceDesignSystem = "true";
  document.head.append(design);
}

const themeStylesheet = new URL("./module-theme.css", import.meta.url).href;
if (!document.querySelector(`link[href="${themeStylesheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = themeStylesheet;
  link.dataset.megaTheme = "true";
  document.head.append(link);
}

function applySuiteSettings(settings) {
  applyGlobalTheme(settings);
  I18n.setLanguage(settings.language);
  document.dispatchEvent(new CustomEvent("workspace:settings-applied", { detail: settings }));
}

async function recordModuleVisit() {
  try {
    const response = await fetch(coreUrl("/api/modules"));
    const modules = (await response.json()).modules || [];
    const current = new URL(location.href);
    const module = modules.find((item) => {
      if (!item.url) return false;
      const target = new URL(item.url, current);
      if (target.origin !== current.origin) return false;
      return target.origin !== CORE_ORIGIN || current.pathname.startsWith(`/module/${item.id}/`);
    });
    if (!module) return;
    const visitKey = `workspace.activity.last-visit.${module.id}`;
    const previous = Number(sessionStorage.getItem(visitKey) || 0);
    if (Date.now() - previous < 30_000) return;
    sessionStorage.setItem(visitKey, String(Date.now()));
    Activity.record({
      kind: "module", level: "info", title: `Módulo aberto: ${module.name}`,
      detail: module.description, moduleId: module.id, url: new URL(module.url, current).href,
    }).catch(() => {});
  } catch { /* atividade recente é opcional */ }
}

Settings.subscribe((settings) => applySuiteSettings(settings), { immediate: false });
Settings.init()
  .then((settings) => applySuiteSettings(settings))
  .catch((error) => Events.emit("settings:error", { error }));

function prepareModuleShell() {
  observeButtonTypes();
  if (!document.querySelector("[data-workspace-home]")) {
    const home = document.createElement("a");
    home.className = "mega-home-link";
    home.href = coreUrl("/");
    home.dataset.workspaceHome = "true";
    home.setAttribute("aria-label", "Voltar ao Workspace OS");
    home.textContent = "← Workspace";
    document.body.append(home);
  }
  if (document.documentElement.dataset.globalTerminal !== "off" && !document.querySelector(".workspace-terminal-host")) {
    globalThis.WorkspaceTerminal = mountTerminal();
  }
  if (document.documentElement.dataset.globalDropzone !== "off" && !document.querySelector(".workspace-drop-host")) {
    globalThis.WorkspaceDropzone = mountUniversalDropzone();
  }
  if (document.documentElement.dataset.globalActivity !== "off" && !document.querySelector(".workspace-activity-host")) {
    globalThis.WorkspaceActivity = mountActivityCenter();
  }
  mountShortcuts();
  I18n.observe();
  BlackBox.start(document.documentElement.dataset.moduleId || document.title);
  observeExports({ moduleId: document.documentElement.dataset.moduleId || "" });
  recordModuleVisit();
  deliverIncomingDrop().catch((error) => Events.emit("dropzone:error", { error }));
  document.addEventListener("change", (event) => {
    if (!event.isTrusted || !(event.target instanceof HTMLInputElement) || event.target.type !== "file") return;
    for (const file of [...(event.target.files || [])].slice(0, 10)) {
      if (file.size <= 100 * 1024 * 1024) {
        storeDropFile(file).then(() => Activity.record({
          kind: "file", level: "info", title: `Arquivo recente: ${file.name}`,
          detail: document.title, moduleId: document.documentElement.dataset.moduleId || "",
        })).catch(() => {});
      }
    }
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", prepareModuleShell, { once: true });
} else {
  prepareModuleShell();
}

globalThis.Mega = Object.freeze({
  settings: Settings,
  events: Events,
  storage: { namespace: createNamespace },
  theme: { apply: applyGlobalTheme, derivePalette },
  ui: { confirm: confirmDialog, toast },
  activity: Activity,
  presets: Presets,
  clipboard: Clipboard,
  backup: ModuleData,
  i18n: I18n,
  blackbox: BlackBox,
  dropzone: { getIncoming: getIncomingDrop, getIncomingFolder: getDropFolder, deliver: deliverIncomingDrop, stage: storeDropFile, send: sendDropFile },
});
