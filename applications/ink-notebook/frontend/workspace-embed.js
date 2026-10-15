const rawOrigin = String(globalThis.__WORKSPACE_CORE_ORIGIN__ || "").trim();

function approvedCoreOrigin(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)
      ? url.origin
      : "";
  } catch {
    return "";
  }
}

const coreOrigin = approvedCoreOrigin(rawOrigin);
const notice = document.querySelector(".workspace-theme-notice");

function applyWorkspaceTheme(payload) {
  const root = document.documentElement;
  root.dataset.theme = payload.theme === "dark" ? "dark" : "light";
  for (const [name, value] of Object.entries(payload.variables || {})) {
    if (name.startsWith("--") && typeof value === "string") root.style.setProperty(name, value);
  }
  root.dataset.workspaceIntegrated = "true";
  if (notice) notice.hidden = false;
}

if (coreOrigin && window.parent !== window) {
  window.addEventListener("message", (event) => {
    if (event.origin !== coreOrigin || event.data?.type !== "workspace:notebook-theme") return;
    applyWorkspaceTheme(event.data);
  });
  window.parent.postMessage({ type: "workspace:notebook-ready" }, coreOrigin);
} else if (notice) {
  notice.hidden = true;
}
