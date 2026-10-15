import { mountTerminal } from "http://127.0.0.1:8790/core/components/terminal.js";

mountTerminal({ target: document.querySelector("#terminal-root"), embedded: true });
