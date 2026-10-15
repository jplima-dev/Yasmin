"use strict";

const { runPython } = require("./python-runner.js");

process.exitCode = runPython(["-m", "workspace_os.module_sdk", "create", ...process.argv.slice(2)]);
