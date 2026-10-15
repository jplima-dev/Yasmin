import assert from "node:assert/strict";
import test from "node:test";

import { openModule } from "../web/module-navigation.js";

function fakeWindow() {
  const calls = { assigned: [], opened: [] };
  return {
    calls,
    location: { assign: (url) => calls.assigned.push(url) },
    open: (...args) => calls.opened.push(args),
  };
}

test("o Conversor de Arquivos abre na guia atual", () => {
  const browserWindow = fakeWindow();

  assert.equal(openModule({ id: "converter", url: "/module/converter/" }, browserWindow), true);
  assert.deepEqual(browserWindow.calls.assigned, ["/module/converter/"]);
  assert.deepEqual(browserWindow.calls.opened, []);
});

test("os demais módulos também abrem na guia atual", () => {
  const browserWindow = fakeWindow();

  assert.equal(openModule({ id: "qrcode", url: "/module/qrcode/" }, browserWindow), true);
  assert.deepEqual(browserWindow.calls.assigned, ["/module/qrcode/"]);
  assert.deepEqual(browserWindow.calls.opened, []);
});

test("módulo sem URL não inicia navegação", () => {
  const browserWindow = fakeWindow();

  assert.equal(openModule({ id: "converter" }, browserWindow), false);
  assert.deepEqual(browserWindow.calls, { assigned: [], opened: [] });
});

test("módulo desativado ou incompatível não abre", () => {
  const browserWindow = fakeWindow();
  assert.equal(openModule({ id: "photos", url: "/module/photos/", enabled: false }, browserWindow), false);
  assert.equal(openModule({ id: "photos", url: "/module/photos/", compatible: false }, browserWindow), false);
  assert.deepEqual(browserWindow.calls.assigned, []);
});
