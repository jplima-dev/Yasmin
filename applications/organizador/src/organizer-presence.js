// Importe este arquivo UMA vez no ponto de entrada principal do seu app Vite.
// Ex.: import "./organizer-presence.js";

const AGENT_WS = "ws://127.0.0.1:8765";

let socket = null;
let leavingPage = false;
let reconnectTimer = null;

function connectToOrganizerAgent() {
  leavingPage = false;

  if (
    socket &&
    (socket.readyState === WebSocket.OPEN ||
      socket.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }

  socket = new WebSocket(AGENT_WS);

  socket.addEventListener("open", () => {
    socket.send(JSON.stringify({ type: "app_open" }));
  });

  socket.addEventListener("close", () => {
    socket = null;

    // Se foi refresh/fechamento/navegação, o navegador já está saindo.
    // Se o agente reiniciar enquanto a página continua aberta, reconecta.
    if (!leavingPage) {
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connectToOrganizerAgent, 1500);
    }
  });
}

window.addEventListener("pagehide", () => {
  leavingPage = true;
  clearTimeout(reconnectTimer);

  if (socket && socket.readyState <= WebSocket.OPEN) {
    socket.close(1000, "pagehide");
  }
});

// Ajuda quando o navegador restaura a página pelo back/forward cache.
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    leavingPage = false;
    connectToOrganizerAgent();
  }
});

connectToOrganizerAgent();
