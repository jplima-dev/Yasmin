"use strict";

const path = require("node:path");
const { spawnSync } = require("node:child_process");

const workspaceRoot = path.resolve(__dirname, "..");

function candidates() {
  const result = [];
  if (process.env.WORKSPACE_PYTHON) result.push({ command: process.env.WORKSPACE_PYTHON, prefix: [] });
  if (process.platform === "win32") {
    result.push(
      { command: path.resolve(workspaceRoot, "..", "bridge", ".venv", "Scripts", "python.exe"), prefix: [] },
      { command: path.resolve(workspaceRoot, "..", "driver", ".venv", "Scripts", "python.exe"), prefix: [] },
      { command: "py", prefix: ["-3"] },
      { command: "python", prefix: [] },
    );
  } else {
    result.push(
      { command: path.resolve(workspaceRoot, "..", "bridge", ".venv", "bin", "python"), prefix: [] },
      { command: path.resolve(workspaceRoot, "..", "driver", ".venv", "bin", "python"), prefix: [] },
      { command: "python3", prefix: [] },
      { command: "python", prefix: [] },
    );
  }
  return result;
}

function findPython() {
  for (const candidate of candidates()) {
    const probe = spawnSync(candidate.command, [...candidate.prefix, "-c", "import sys; raise SystemExit(sys.version_info < (3, 11))"], {
      cwd: workspaceRoot,
      stdio: "ignore",
      windowsHide: true,
    });
    if (!probe.error && probe.status === 0) return candidate;
  }
  return null;
}

function runPython(args, options = {}) {
  const python = findPython();
  if (!python) {
    console.error("Python 3.11+ não foi encontrado. Configure WORKSPACE_PYTHON ou prepare a .venv do Bridge/InkDriver.");
    return 1;
  }
  const result = spawnSync(python.command, [...python.prefix, ...args], {
    cwd: options.cwd || workspaceRoot,
    stdio: options.stdio || "inherit",
    windowsHide: true,
    env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
  });
  if (result.error) {
    console.error(`Falha ao executar Python: ${result.error.message}`);
    return 1;
  }
  return result.status ?? 1;
}

module.exports = { findPython, runPython, workspaceRoot };

if (require.main === module) {
  process.exitCode = runPython(process.argv.slice(2));
}
