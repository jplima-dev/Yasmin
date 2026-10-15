import { analyzeDirectory, analyzeFileList } from "./analyzer-engine.js";
import { getDropFolder } from "http://127.0.0.1:8790/core/dropzone.js";

const LANGUAGE_KEY = "analisador-projetos.language";

function selectDirectoryFiles() {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    input.setAttribute("webkitdirectory", "");
    input.hidden = true;
    document.body.append(input);
    let settled = false;
    const finish = (files) => {
      if (settled) return;
      settled = true;
      input.remove();
      resolve(files);
    };
    input.addEventListener("change", () => finish(input.files), { once: true });
    input.addEventListener("cancel", () => finish(null), { once: true });
    window.addEventListener("focus", () => window.setTimeout(() => {
      if (!settled && !input.files?.length) finish(null);
    }, 400), { once: true });
    input.click();
  });
}

export const BrowserAnalyzerApi = {
  async get_settings() {
    return { ok: true, language: localStorage.getItem(LANGUAGE_KEY) || "pt", settings_path: "Armazenamento local do navegador" };
  },
  async set_language(language) {
    if (!["pt", "en"].includes(language)) return { ok: false, error: "Unsupported language." };
    localStorage.setItem(LANGUAGE_KEY, language);
    return { ok: true, language };
  },
  async select_project() {
    try {
      if ("showDirectoryPicker" in window) {
        const handle = await window.showDirectoryPicker({ mode: "read", id: "analisador-projetos" });
        return { ok: true, data: await analyzeDirectory(handle) };
      }
      const files = await selectDirectoryFiles();
      if (!files?.length) return { ok: false, cancelled: true };
      return { ok: true, data: await analyzeFileList(files) };
    } catch (error) {
      if (error?.name === "AbortError") return { ok: false, cancelled: true };
      return { ok: false, error: error?.message || String(error) };
    }
  },
  async open_workspace_folder(folderId) {
    try {
      const folder = await getDropFolder(folderId);
      return { ok: true, data: await analyzeFileList(folder.files) };
    } catch (error) {
      return { ok: false, error: error?.message || String(error) };
    }
  },
};

globalThis.BrowserAnalyzerApi = BrowserAnalyzerApi;
