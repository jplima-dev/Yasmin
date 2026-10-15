import assert from "node:assert/strict";
import test from "node:test";
import { planAI, isSensitiveName, parseExtensions, readFileList, safeName } from "../web/js/project-reader.js";

test("normaliza extensões configuradas", () => {
  assert.deepEqual(parseExtensions(".js, TS; py"), [".js", ".ts", ".py"]);
});

test("bloqueia nomes com risco de segredo", () => {
  assert.equal(isSensitiveName(".env.local"), true);
  assert.equal(isSensitiveName("private.pem"), true);
  assert.equal(isSensitiveName("app.js"), false);
});

test("gera Markdown organizado e dividido por limite", () => {
  const files = [
    { path: "src/a.js", text: "a".repeat(2500), language: "javascript", selected: true },
    { path: "src/b.js", text: "b".repeat(2500), language: "javascript", selected: true },
  ];
  const { parts } = planAI(files, { name: "Meu Projeto", tokenLimit: 1000, includeTree: true });
  assert.equal(parts.length, 2);
  assert.match(parts[0].text, /^# Projeto: Meu Projeto/);
  assert.match(parts.map(part => part.text).join(""), /## src\/b\.js/);
});

test("cria nome seguro para download", () => assert.equal(safeName("Projeto Café"), "projeto-cafe"));

test("fallback de pasta mantém código e bloqueia .env", async () => {
  const source = new Blob(["console.log('ok')"]);
  Object.defineProperties(source, { name: { value: "APP.JS" }, webkitRelativePath: { value: "Projeto/src/APP.JS" } });
  const secret = new Blob(["TOKEN=segredo"]);
  Object.defineProperties(secret, { name: { value: ".env" }, webkitRelativePath: { value: "Projeto/.env" } });
  const result = await readFileList([source, secret], {
    extensions: parseExtensions("js,env"), ignoredFolders: [], ignoredFiles: []
  });
  assert.equal(result.name, "Projeto");
  assert.equal(result.files.length, 1);
  assert.equal(result.sensitive, 1);
});
