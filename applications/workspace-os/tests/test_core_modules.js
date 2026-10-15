import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { displayNameFromFolder, validateModuleManifest } from "../web/core/modules.js";
import { applyGlobalTheme, derivePalette, normalizeHex } from "../web/core/theme.js";

const workspaceStyles = await readFile(new URL("../web/styles.css", import.meta.url), "utf8");
const workspaceHtml = await readFile(new URL("../web/index.html", import.meta.url), "utf8");
const terminalSource = await readFile(new URL("../web/core/components/terminal.js", import.meta.url), "utf8");
const splitViewSource = await readFile(new URL("../web/core/split-view.js", import.meta.url), "utf8");
const splitPageSource = await readFile(new URL("../web/core/split-page.js", import.meta.url), "utf8");
const splitViewStyles = await readFile(new URL("../web/core/split-view.css", import.meta.url), "utf8");
const activityCenterSource = await readFile(new URL("../web/core/components/activity-center.js", import.meta.url), "utf8");
const activityCenterStyles = await readFile(new URL("../web/core/components/activity-center.css", import.meta.url), "utf8");
const themePreload = await readFile(new URL("../web/core/theme-preload.js", import.meta.url), "utf8");
const themeSource = await readFile(new URL("../web/core/theme.js", import.meta.url), "utf8");

test("nomes de pastas viram nomes naturais", () => {
  assert.equal(displayNameFromFolder("notas-flutuantes"), "Notas Flutuantes");
  assert.equal(displayNameFromFolder("analisador-projetos"), "Analisador de Projetos");
  assert.equal(displayNameFromFolder("ink_write"), "Ink Write");
});

test("manifesto exige campos do contrato público", () => {
  assert.equal(validateModuleManifest({ id: "qr", name: "QR", kind: "static-web" }).id, "qr");
  assert.throws(() => validateModuleManifest({ id: "qr" }), /name/);
});

test("paleta deriva hover, fundos e cores companheiras da cor livre", () => {
  const palette = derivePalette("#336699", "light");
  assert.equal(palette.accent, "#336699");
  assert.equal(palette.secondary, "#669933");
  assert.equal(palette.tertiary, "#993366");
  assert.match(palette.hover, /^#[0-9a-f]{6}$/);
  assert.notEqual(palette.soft, palette.accent);
  assert.equal(normalizeHex("inválida"), "#ff5b3d");
});

test("identidade visual não sobrescreve a coluna única em telas pequenas", () => {
  assert.match(workspaceStyles, /@media \(max-width: 760px\)[\s\S]*?\.app-shell \{ grid-template-columns: 1fr; \}/);
  assert.match(workspaceStyles, /@media \(min-width: 761px\) \{\s*\.app-shell \{ grid-template-columns: 180px minmax\(0, 1fr\); \}/);
  assert.doesNotMatch(workspaceStyles, /\n\.app-shell \{ grid-template-columns: 180px/);
});

test("terminal reconhece a folha de estilo já declarada pela Home", () => {
  assert.match(workspaceHtml, /data-workspace-terminal-style/);
  assert.match(terminalSource, /data-workspace-terminal-style/);
});

test("terminal aceita home e open home como o mesmo comando", () => {
  assert.match(terminalSource, /normalized === "home" \|\| normalized === "open home"/);
});

test("falhas do terminal usam uma única caixa preta expansível", () => {
  assert.match(terminalSource, /workspace-terminal-blackbox/);
  assert.match(terminalSource, /summary\.textContent = "caixa preta: erro"/);
  assert.match(terminalSource, /appendBlackBoxError\(/);
  assert.doesNotMatch(terminalSource, /Activity\.record/);
});

test("terminal mantém processos por aba e permite cancelar e exportar", () => {
  assert.match(terminalSource, /session\.executionId/);
  assert.match(terminalSource, /\/api\/terminal\/processes/);
  assert.match(terminalSource, /method: "DELETE"/);
  assert.match(terminalSource, /function exportSession/);
  assert.match(terminalSource, /data-terminal-cancel/);
});

test("terminal completa com comandos reais e limita o histórico", () => {
  assert.match(terminalSource, /\/api\/terminal\/completions/);
  assert.match(terminalSource, /authenticated: protectedRead/);
  assert.match(terminalSource, /const HISTORY_LIMIT = 50/);
  assert.match(terminalSource, /SENSITIVE_COMMAND/);
  assert.match(terminalSource, /Histórico do Ink Terminal removido com segurança/);
});

test("subdivide cria duas instâncias e unsubidivide exige escolher uma", () => {
  assert.match(terminalSource, /normalized === "subdivide"/);
  assert.match(terminalSource, /normalized === "unsubidivide" \|\| normalized === "unsubdivide"/);
  assert.match(splitViewSource, /createPane\(cleanPaneUrl\(source\.href\), "one", "Tela 1"\)/);
  assert.match(splitViewSource, /createPane\(cleanPaneUrl\(source\.href\), "two", "Tela 2"\)/);
  assert.doesNotMatch(splitViewSource, /replaceChildren/);
  assert.match(splitViewSource, /element\.parentNode !== state\.shell/);
  assert.match(splitViewSource, /Qual tela deve continuar\?/);
  assert.match(splitViewSource, /workspace:split-view/);
  assert.match(splitPageSource, /source\.origin !== location\.origin/);
  assert.match(splitViewStyles, /workspace-split-divider/);
});

test("Central do Workspace não exibe badge para atividades comuns", () => {
  assert.doesNotMatch(activityCenterSource, /data-activity-badge|const badge|badge\.(hidden|textContent)/);
  assert.doesNotMatch(activityCenterStyles, /workspace-activity-launcher span/);
  assert.match(activityCenterSource, /data-center-tab="blackbox">Caixa-preta/);
});

test("preload e tema definitivo compartilham a mesma superfície de hover", () => {
  for (const color of ["#24272d", "#e8e1d3"]) {
    assert.match(themePreload, new RegExp(color));
    assert.match(themeSource, new RegExp(color));
  }
  assert.match(themePreload, /--ws-color-surface-hover"\s*:\s*colors\.surfaceHover/);
});

test("tema automático observa mudanças do sistema operacional", () => {
  let dark = false;
  let mediaListener;
  const media = {
    get matches() { return dark; },
    addEventListener(type, listener) { if (type === "change") mediaListener = listener; },
  };
  const previousMatchMedia = globalThis.matchMedia;
  globalThis.matchMedia = () => media;
  const properties = new Map();
  const root = {
    dataset: {},
    style: { setProperty(name, value) { properties.set(name, value); } },
    ownerDocument: {
      defaultView: { matchMedia: () => media },
      body: { classList: { toggle() {} } },
    },
  };
  const settings = { theme: "system", accent: "#336699", density: "comfortable", font_size: "comfortable", language: "pt-BR" };
  try {
    applyGlobalTheme(settings, root);
    assert.equal(root.dataset.theme, "light");
    assert.equal(typeof mediaListener, "function");
    dark = true;
    mediaListener();
    assert.equal(root.dataset.theme, "dark");
    assert.equal(properties.get("--ws-color-surface-hover"), "#24272d");
  } finally {
    globalThis.matchMedia = previousMatchMedia;
  }
});
