"use strict";

const { runPython } = require("./python-runner.js");

process.exitCode = runPython(["launcher.py", "--doctor", ...process.argv.slice(2)]);
