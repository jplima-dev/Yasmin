import assert from "node:assert/strict";
import test from "node:test";

import { buildCommands, filterCommands, normalizeSearch } from "../web/command-palette.js";

test("busca ignora acentos e caixa", () => {
  assert.equal(normalizeSearch("  Configurações  "), "configuracoes");
});

test("catálogo combina rotas e módulos instalados", () => {
  const commands = buildCommands([{ id: "qrcode", name: "Gerador de QR Code", kind: "static-web", category: "utilities", description: "Gera códigos", reachable: true }]);
  assert.ok(commands.some((command) => command.route === "settings"));
  assert.ok(commands.some((command) => command.moduleId === "qrcode" && command.action === "open"));
});

test("busca encontra ações por descrição e limita resultados", () => {
  const commands = buildCommands([
    { id: "bridge", name: "Bridge", kind: "web-service", category: "devices", description: "Transferência entre dispositivos", reachable: false, canStart: true },
  ]);
  assert.equal(filterCommands(commands, "transferencia")[0].moduleId, "bridge");
  assert.equal(filterCommands(commands, "", 2).length, 2);
});

test("busca inclui terminal, Drop Zone e palavras-chave específicas dos módulos", () => {
  const commands = buildCommands([
    { id: "json", name: "Ink JSON", kind: "static-web", category: "utilities", description: "Editor estruturado", reachable: true, keywords: ["minificar", "validar"] },
  ]);
  assert.equal(filterCommands(commands, "terminal")[0].action, "terminal");
  assert.equal(filterCommands(commands, "arrastar arquivo")[0].action, "dropzone");
  assert.equal(filterCommands(commands, "minificar")[0].moduleId, "json");
});

test("busca inclui atividades e backup do Workspace", () => {
  const commands = buildCommands([]);
  assert.equal(filterCommands(commands, "notificações")[0]?.action, "activity");
  assert.equal(filterCommands(commands, "backup")[0]?.action, "backup");
});

test("busca global inclui módulos usados e arquivos recentes", () => {
  const commands = buildCommands([], {
    activities: [{ id: "a1", kind: "module", moduleId: "json", title: "Módulo aberto: Ink JSON", detail: "Editor JSON", url: "http://127.0.0.1:8790/module/json/index.html" }],
    dropItems: [{ id: "f1", name: "dados-clientes.csv", type: "text/csv", kind: "file" }],
  });
  assert.equal(filterCommands(commands, "Ink JSON")[0]?.action, "open-url");
  assert.equal(filterCommands(commands, "dados clientes")[0]?.action, "dropzone");
});
