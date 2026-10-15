import { Settings } from "./settings.js";

function matches(event, shortcut) {
  const parts = String(shortcut || "").toLowerCase().split("+").map((part) => part.trim()).filter(Boolean);
  const key = parts.at(-1);
  if (!key) return false;
  const expected = key === "space" ? " " : key;
  return String(event?.key || "").toLowerCase() === expected
    && Boolean(event?.ctrlKey) === (parts.includes("ctrl") || parts.includes("control"))
    && Boolean(event?.altKey) === parts.includes("alt")
    && Boolean(event?.shiftKey) === parts.includes("shift")
    && Boolean(event?.metaKey) === (parts.includes("meta") || parts.includes("cmd"));
}

export function mountShortcuts({ search } = {}) {
  if (document.documentElement.dataset.workspaceShortcuts === "mounted") return;
  document.documentElement.dataset.workspaceShortcuts = "mounted";
  document.addEventListener("keydown", (event) => {
    const shortcuts = Settings.get("keyboard_shortcuts") || {};
    const active = document.activeElement;
    const editing = active?.matches?.("input, textarea, select, [contenteditable='true']");
    if (matches(event, shortcuts.search)) { event.preventDefault(); search?.(); return; }
    if (editing) return;
    if (matches(event, shortcuts.terminal)) {
      event.preventDefault();
      const terminal = globalThis.WorkspaceTerminal;
      if (terminal) terminal.element.hidden ? terminal.open() : terminal.close();
    } else if (matches(event, shortcuts.dropzone)) {
      event.preventDefault(); globalThis.WorkspaceDropzone?.open();
    } else if (matches(event, shortcuts.activities)) {
      event.preventDefault(); globalThis.WorkspaceActivity?.open();
    }
  });
}

export const Shortcut = Object.freeze({ matches });
