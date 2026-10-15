"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { runPython, workspaceRoot } = require("./python-runner.js");

const pythonStatus = runPython(["-m", "unittest", "discover", "-s", "tests", "-v"]);
if (pythonStatus !== 0) {
  process.exitCode = pythonStatus;
} else {
  const files = fs.readdirSync(path.join(workspaceRoot, "tests"))
    .filter((name) => name.endsWith(".js"))
    .map((name) => path.join("tests", name));
  const result = spawnSync(process.execPath, ["--test", ...files], {
    cwd: workspaceRoot,
    stdio: "inherit",
    windowsHide: true,
  });
  process.exitCode = result.error ? 1 : (result.status ?? 1);
}
