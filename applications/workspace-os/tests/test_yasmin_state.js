import assert from "node:assert/strict";
import test from "node:test";
import { deriveYasminVisual, visibleProcesses } from "../web/yasmin-state.js";

test("a fala anima as barras e tem prioridade sobre a execução", () => {
  assert.deepEqual(deriveYasminVisual({ ok: true, falando: true,
    estado_agente: "executando", tarefa_atual: "Analisar projeto" }),
  { mode: "speaking", text: "Yasmin falando" });
  assert.equal(deriveYasminVisual({ ok: true, estado_voz: "respondendo" }).mode,
               "speaking");
});

test("a tarefa em curso expõe a etapa no indicador", () => {
  assert.deepEqual(deriveYasminVisual({ ok: true, estado_agente: "executando",
    tarefa_atual: "Exportar contexto do projeto" }),
  { mode: "working", text: "Exportar contexto do projeto" });
  assert.equal(deriveYasminVisual({ ok: true }, true).mode, "working");
  assert.equal(deriveYasminVisual({ ok: false }, true).mode, "working");
  assert.equal(deriveYasminVisual({ ok: true, falando: true,
    estado_agente: "concluido" }, true).mode, "working");
});

test("mostra apenas os dois processos recentes e estruturados", () => {
  assert.deepEqual(visibleProcesses({ processos: [
    { descricao: "Planejando", status: "concluido" },
    null,
    { descricao: "Analisando", status: "executando" },
    { descricao: "Verificando", status: "executando" },
  ] }), [
    { descricao: "Analisando", status: "executando" },
    { descricao: "Verificando", status: "executando" },
  ]);
});

test("conexão ausente e escuta possuem estados distintos", () => {
  assert.equal(deriveYasminVisual({}).mode, "offline");
  assert.equal(deriveYasminVisual({ ok: true, microfone: { erro: "driver" } }).text,
               "Microfone indisponível · use a conversa");
  assert.equal(deriveYasminVisual({ ok: true, estado_voz: "escutando_comando" }).mode,
               "listening");
});
