import assert from "node:assert/strict";
import test from "node:test";

globalThis.location ||= { port: "8790" };

const { Shortcut } = await import("../web/core/shortcuts.js");

test("atalho ignora eventos que nao possuem tecla", () => {
  assert.equal(Shortcut.matches({}, "Ctrl+K"), false);
  assert.equal(Shortcut.matches({ key: undefined }, "Ctrl+K"), false);
});

test("atalho continua reconhecendo teclas e modificadores", () => {
  assert.equal(Shortcut.matches({ key: "K", ctrlKey: true }, "Ctrl+K"), true);
  assert.equal(Shortcut.matches({ key: "K" }, "Ctrl+K"), false);
});
