"use strict";

export function deriveYasminVisual(state = {}, busy = false) {
  if (busy) return { mode: "working", text: state.tarefa_atual || "Preparando tarefa" };
  if (state.falando === true || (state.falando == null && state.estado_voz === "respondendo")) {
    return { mode: "speaking", text: "Yasmin falando" };
  }
  if (["interpretando", "planejando", "executando"].includes(state.estado_agente)) {
    return { mode: "working", text: state.tarefa_atual || "Preparando tarefa" };
  }
  if (state.ok !== true) return { mode: "offline", text: "Aguardando Yasmin" };
  if (state.estado_agente === "falhou") return { mode: "idle", text: "Tarefa falhou · veja a conversa" };
  if (state.estado_agente === "bloqueado") return { mode: "idle", text: "Preciso de mais informações" };
  if (state.microfone?.erro) return { mode: "idle", text: "Microfone indisponível · use a conversa" };
  if (state.estado_voz === "escutando_comando") return { mode: "listening", text: "Ouvindo você" };
  return { mode: "idle", text: "Pronta para ajudar" };
}

export function visibleProcesses(state = {}) {
  if (!Array.isArray(state.processos)) return [];
  return state.processos.filter((item) => item && typeof item.descricao === "string" &&
    typeof item.status === "string").slice(-2);
}
