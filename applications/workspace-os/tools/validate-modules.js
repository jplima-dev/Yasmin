"use strict";

const { runPython } = require("./python-runner.js");

process.exitCode = runPython(["-m", "workspace_os.module_sdk", "validate", ...process.argv.slice(2)]);
