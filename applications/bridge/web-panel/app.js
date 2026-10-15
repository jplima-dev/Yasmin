const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

function storedDeviceId() {
  try {
    const local = localStorage.getItem("bridge.deviceId");
    if (local) return local;
  } catch { }
  const cookie = document.cookie.split(";").map(part => part.trim()).find(part => part.startsWith("bridge.deviceId="));
  return cookie ? decodeURIComponent(cookie.slice("bridge.deviceId=".length)) : null;
}

function rememberDevice(deviceId, name = "") {
  try {
    localStorage.setItem("bridge.deviceId", deviceId);
    if (name) localStorage.setItem("bridge.deviceName", name);
  } catch { }
  document.cookie = `bridge.deviceId=${encodeURIComponent(deviceId)}; Max-Age=31536000; Path=/; SameSite=Strict`;
}

function forgetDevice() {
  try { localStorage.removeItem("bridge.deviceId"); } catch { }
  document.cookie = "bridge.deviceId=; Max-Age=0; Path=/; SameSite=Strict";
}

const state = {
  deviceId: storedDeviceId(), devices: [], transfers: [], ws: null, pairing: null,
  installPrompt: null, urlTarget: null, uploads: new Map(), resumeTransferId: null,
  screenSession: null, pendingScreenCommand: null, pendingUrlCommand: null,
  pendingActions: new Set(),
};

const SCREEN_REQUEST_TIMEOUT_MS = 5 * 60 * 1000;

const EVENT_LABELS = {
  pairing_requested: "Aparelho solicitou cadastro", pairing_confirmed: "Aparelho adicionado",
  pairing_failed: "Cadastro recusado", device_revoked: "Aparelho removido",
  permissions_changed: "Permissões atualizadas", transfer_offered: "Envio iniciado",
  transfer_completed: "Arquivo entregue", transfer_pause: "Envio pausado",
  transfer_resume: "Envio retomado", transfer_cancel: "Envio cancelado",
  integrity_failed: "Falha ao verificar arquivo", text: "Texto enviado", snippet: "Trecho enviado",
  link: "Link enviado", clipboard: "Clipboard enviado", photo_offer: "Foto oferecida",
  command_issued: "Ação enviada", command_result: "Ação concluída", command_denied: "Ação recusada",
  sensitive_action_challenge: "Ação sensível confirmada", file_requested: "Arquivo solicitado",
  team_member_changed: "Participação em equipe alterada", notification_action: "Decisão de notificação",
  p2p_signal: "Conexão direta negociada", rule_applied: "Automação executada", drive2_queued: "Arquivo preparado para o Drive2",
  screen_handoff_claimed: "Solicitação de tela aberta no navegador",
  remote_control_started: "Controle remoto autorizado",
  remote_control_ended: "Controle remoto encerrado",
};

const ACTION_LABELS = {
  open_url: "abrir URL", screen_start: "ver tela", screen_stop: "parar transmissão de tela",
  ring: "tocar som", lock: "bloquear", notify: "mostrar notificação", open_folder: "abrir pasta",
  request_photo: "pedir foto",
};

const STATUS_LABELS = {
  created: "registrado", sent: "enviado", accepted: "aceito", completed: "concluído",
  denied: "recusado", failed: "falhou", offered: "enviando", receiving: "recebendo",
  verifying: "verificando", paused: "pausado", cancelled: "cancelado", integrity_failed: "arquivo inválido",
};

class ApiError extends Error {
  constructor(message, status, detail = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { ...(options.body && !(options.body instanceof Blob) ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) },
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    let rawDetail = null;
    try {
      const body = await response.json();
      rawDetail = body.detail;
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { }
    throw new ApiError(detail, response.status, rawDetail);
  }
  if (response.status === 204) return null;
  return response.json();
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

function toast(message, error = false) {
  const node = document.createElement("div");
  node.className = `toast${error ? " error" : ""}`;
  node.textContent = message;
  $("#toasts").append(node);
  setTimeout(() => node.remove(), 4500);
}

function formatTime(value) {
  if (!value) return "nunca";
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function randomUuid() {
  if (typeof window.crypto?.randomUUID === "function") return window.crypto.randomUUID();

  const bytes = new Uint8Array(16);
  if (typeof window.crypto?.getRandomValues === "function") window.crypto.getRandomValues(bytes);
  else {
    const seed = Date.now();
    for (let index = 0; index < bytes.length; index++) bytes[index] = Math.floor(Math.random() * 256) ^ (seed >>> (index % 6 * 8));
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map(byte => byte.toString(16).padStart(2, "0"));
  return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
}

function iconFor(type) { return ({ windows: "▰", android: "▯", tablet: "▤", web: "◎", server: "⬡" })[type] || "◇"; }
function humanKind(kind) { return kind.replaceAll("_", " ").replace(/^./, c => c.toUpperCase()); }

function setConnection(status, text) {
  $("#connectionDot").className = `dot ${status}`;
  $("#connectionText").textContent = text;
}

function currentNetworkType() {
  const host = location.hostname.toLowerCase();
  if (host.endsWith(".ts.net")) return "tailscale";
  const octets = host.split(".").map(Number);
  if (octets.length === 4 && octets[0] === 100 && octets[1] >= 64 && octets[1] <= 127) return "tailscale";
  return "lan";
}

function showView(name) {
  if (!document.getElementById(name)) name = "devices";
  $$(".view").forEach(view => view.classList.toggle("active", view.id === name));
  $$(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.view === name));
  if (name === "history") loadHistory();
  if (name === "settings") loadNetwork();
}

function route() { showView(location.hash.slice(1) || "devices"); }
window.addEventListener("hashchange", route);

async function ensureIdentity() {
  if (state.deviceId) {
    try {
      const devices = await api("/devices");
      if (devices.some(device => device.id === state.deviceId)) {
        rememberDevice(state.deviceId);
        return;
      }
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
    }
    forgetDevice(); state.deviceId = null;
  }
  resetPairDialog();
  $("#pairDialog").showModal();
}

function resetPairDialog() {
  state.pairing = null;
  $("#pairNameStep").hidden = false;
  $("#pairCodeStep").hidden = true;
  $("#pairCode").value = "";
  $("#requestPair").disabled = false;
  $("#requestPair").textContent = "Gerar código de pareamento";
}

async function requestPair() {
  const name = $("#deviceName").value.trim();
  if (!name) return;
  const button = $("#requestPair");
  button.disabled = true;
  button.textContent = "Gerando...";
  try {
    state.pairing = await api("/pairing/request", {
      method: "POST", body: JSON.stringify({
        name, device_type: "web", public_key: `web-${randomUuid()}-${randomUuid()}`,
        permissions: { remote_ring: true, remote_lock: false, screen_share: true, remote_actions: true, photos: true, clipboard: true },
      })
    });
    $("#pairNameStep").hidden = true;
    $("#pairCodeStep").hidden = false;
    $("#pairCode").focus();
    toast("Código gerado. Veja os seis dígitos no Bridge Core.");
  } catch (error) { toast(error.message, true); }
  finally {
    button.disabled = false;
    button.textContent = "Gerar código de pareamento";
  }
}

async function confirmPair(event) {
  event?.preventDefault();
  if (!state.pairing) return;
  const code = $("#pairCode").value.trim();
  if (!/^\d{6}$/.test(code)) return toast("Digite os seis dígitos mostrados no Core.", true);
  const button = $("#confirmPair");
  button.disabled = true;
  button.textContent = "Confirmando...";
  try {
    await api(`/pairing/${state.pairing.device_id}/confirm`, { method: "POST", body: JSON.stringify({ code }) });
    state.deviceId = state.pairing.device_id;
    rememberDevice(state.deviceId, $("#deviceName").value.trim());
    $("#pairDialog").close();
    connectSocket(); await refreshAll(); toast("Este aparelho agora faz parte do Bridge.");
  } catch (error) { toast(error.message, true); }
  finally {
    button.disabled = false;
    button.textContent = "Confirmar aparelho";
  }
}

async function loadDevices() {
  state.devices = await api("/devices");
  const grid = $("#deviceGrid"); grid.classList.remove("skeleton-grid");
  grid.innerHTML = state.devices.length ? state.devices.map(device => `
    <article class="device-card">
      <div class="device-top"><span class="device-icon">${iconFor(device.device_type)}</span>
        <div><h3 class="device-name">${escapeHtml(device.name)}${device.id === state.deviceId ? " · este" : ""}</h3><div class="device-type">${escapeHtml(device.device_type)}</div></div>
        <span class="presence ${device.online ? "online" : ""}" title="${device.online ? "Online" : "Offline"}"></span>
      </div>
      <div class="device-meta"><span class="chip">${device.online ? "Online" : `Visto ${formatTime(device.last_seen)}`}</span><span class="chip">${escapeHtml(device.network_type)}</span>${device.battery != null ? `<span class="chip">${device.battery}%</span>` : ""}${device.activity ? `<span class="chip">${escapeHtml(device.activity)}</span>` : ""}</div>
      <div class="device-actions">${device.id !== state.deviceId ? `<button class="button secondary" data-send="${device.id}">Enviar arquivo</button>` : ""}<button class="button ghost" data-actions="${device.id}">Ações</button></div>
    </article>`).join("") : `<div class="feed empty">Nenhum aparelho pareado.</div>`;
  const targets = state.devices.filter(device => device.id !== state.deviceId && device.pairing_status === "paired");
  const options = targets.map(device => `<option value="${device.id}">${escapeHtml(device.name)}</option>`).join("") || `<option value="">Adicione outro aparelho</option>`;
  $("#messageTarget").innerHTML = options;
  $("#fileTarget").innerHTML = options;
  grid.querySelectorAll("[data-send]").forEach(button => button.onclick = () => {
    $("#fileTarget").value = button.dataset.send;
    location.hash = "send";
    $("#fileInput").click();
  });
  grid.querySelectorAll("[data-actions]").forEach(button => button.onclick = () => openActions(button.dataset.actions));
  syncScreenPermissionUi();
}

function addFeed(kind, payload = {}) {
  const feed = $("#liveFeed"); feed.classList.remove("empty");
  if (feed.textContent.includes("Nenhum evento")) feed.innerHTML = "";
  const item = document.createElement("div"); item.className = "feed-item";
  item.innerHTML = `<span class="timeline-icon">${kind.includes("transfer") ? "↑" : kind.includes("presence") ? "●" : "◇"}</span><div><strong>${escapeHtml(humanKind(kind))}</strong><br><small>${escapeHtml(payload.file_name || payload.action || payload.content || payload.device_id || "Evento recebido")}</small></div>`;
  feed.prepend(item); while (feed.children.length > 8) feed.lastElementChild.remove();
}

async function loadRecentActivity() {
  const items = await api("/history?limit=8&security_only=false");
  const feed = $("#liveFeed");
  if (!items.length) {
    feed.className = "feed empty";
    feed.textContent = "Nenhuma atividade registrada.";
    return;
  }
  feed.className = "feed";
  feed.innerHTML = items.map(item => `<article class="feed-item"><span class="timeline-icon">${item.kind.includes("transfer") ? "↑" : item.security ? "⌾" : "◇"}</span><div><strong>${escapeHtml(EVENT_LABELS[item.kind] || humanKind(item.kind))}</strong><br><small>${escapeHtml(eventDescription(item))} · ${formatTime(item.created_at)}</small></div></article>`).join("");
}

function connectSocket() {
  if (!state.deviceId) return;
  if (state.ws) state.ws.close();
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${location.host}/ws/${state.deviceId}`); state.ws = ws;
  ws.onopen = () => {
    setConnection("live", "Ao vivo"); ws.send(JSON.stringify({
      type: "ping", presence: {
        network_type: currentNetworkType(), activity: "Painel Bridge",
        capabilities: { screen_capture: screenSharingSupported(), webrtc: Boolean(window.RTCPeerConnection) },
      }
    }));
  };
  ws.onclose = () => { setConnection("offline", "Reconectando"); setTimeout(connectSocket, 2500); };
  ws.onerror = () => setConnection("offline", "Sem conexão");
  ws.onmessage = event => {
    const message = JSON.parse(event.data); if (message.type === "pong") return;
    addFeed(message.type, message.payload);
    if (["presence", "devices_changed"].includes(message.type)) loadDevices();
    if (message.type.startsWith("transfer")) {
      loadTransfers();
      if (message.type === "transfer_completed" && message.payload.target_id === state.deviceId) downloadReceivedTransfer(message.payload);
      else toast(message.type === "transfer_completed" ? "Transferência concluída e verificada." : "Atualização de transferência.");
    }
    if (message.type === "message") toast(`Novo ${humanKind(message.payload.kind)} recebido.`);
    if (message.type === "command") handleBrowserCommand(message.payload);
    if (message.type === "webrtc_signal") handleWebRtcSignal(message.payload);
    if (message.type === "control_status") handleControlStatus(message.payload);
  };
}

function currentDevice() {
  return state.devices.find(device => device.id === state.deviceId) || null;
}

function screenSharingSupported() {
  return Boolean(window.RTCPeerConnection && navigator.mediaDevices?.getDisplayMedia);
}

function syncScreenPermissionUi() {
  const toggle = $("#screenSharePermission");
  const hint = $("#screenShareHint");
  if (!toggle || !hint) return;
  const device = currentDevice();
  const supported = screenSharingSupported();
  toggle.checked = Boolean(device?.permissions?.screen_share);
  toggle.disabled = !device;
  if (supported) {
    hint.textContent = "Navegador pronto para compartilhar. Mesmo ativado, cada transmissão exige aprovação local.";
  } else if (!window.isSecureContext) {
    hint.textContent = "A preferência pode ser salva, mas a captura exige abrir o painel do computador por http://127.0.0.1:8876 ou HTTPS.";
  } else {
    hint.textContent = "A preferência pode ser salva, mas este navegador não captura tela. Use Chrome ou Edge no computador.";
  }
}

async function updateScreenPermission(event) {
  const toggle = event.currentTarget;
  const device = currentDevice();
  if (!device) return;
  const previous = Boolean(device.permissions?.screen_share);
  toggle.disabled = true;
  try {
    const permissions = { ...(device.permissions || {}), screen_share: toggle.checked };
    await api(`/devices/${state.deviceId}/permissions`, { method: "PATCH", body: JSON.stringify(permissions) });
    device.permissions = permissions;
    toast(toggle.checked ? "Solicitações de tela permitidas neste navegador." : "Solicitações de tela bloqueadas neste navegador.");
  } catch (error) {
    toggle.checked = previous;
    toast(error.message, true);
  } finally {
    syncScreenPermissionUi();
  }
}

function sendCommandResult(command, status, detail) {
  if (state.ws?.readyState !== WebSocket.OPEN) return;
  state.ws.send(JSON.stringify({ type: "command_result", payload: { command_id: command.id, action: command.action, status, detail } }));
}

async function sendScreenSignal(targetId, kind, payload) {
  return api("/signals", { method: "POST", body: JSON.stringify({ source_id: state.deviceId, target_id: targetId, kind, payload }) });
}

function screenDeviceName(deviceId) {
  return state.devices.find(device => device.id === deviceId)?.name || "Outro aparelho";
}

function setScreenViewerStatus(text) {
  $("#screenViewerStatus").textContent = text;
}

function showScreenViewer(session) {
  $("#screenViewerTitle").textContent = `Tela de ${screenDeviceName(session.remoteDeviceId)}`;
  setScreenViewerStatus(matchMedia("(orientation: portrait)").matches
    ? "Aguardando aprovação · para ver maior, use Tela cheia e gire o celular."
    : "Aguardando aprovação no outro aparelho.");
  $("#screenViewerPlaceholder").hidden = false;
  $("#remoteScreen").srcObject = null;
  const dialog = $("#screenViewerDialog");
  if (!dialog.open) dialog.showModal();
}

function closeDialog(selector) {
  const dialog = $(selector);
  if (dialog?.open) dialog.close();
}

function disposeScreenSession({ notifyPeer = false, reason = "Compartilhamento encerrado." } = {}) {
  const session = state.screenSession;
  if (!session) return;
  state.screenSession = null;
  clearTimeout(session.timeout);
  if (notifyPeer) sendScreenSignal(session.remoteDeviceId, "end", { session_id: session.id, reason }).catch(() => { });
  session.peer?.close();
  session.stream?.getTracks().forEach(track => track.stop());
  $("#remoteScreen").srcObject = null;
  $("#localScreen").srcObject = null;
  $("#screenViewerPlaceholder").hidden = false;
  $("#remoteControlBar").hidden = true;
  $("#remoteScreenStage").classList.remove("control-enabled");
  setRightClickArmed(false);
  closeDialog("#screenViewerDialog");
  closeDialog("#screenBroadcastDialog");
  if (document.fullscreenElement) document.exitFullscreen().catch(() => { });
}

function handleControlStatus(payload) {
  const session = state.screenSession;
  if (!session || session.role !== "viewer" || session.id !== payload?.session_id || !payload.enabled) return;
  session.controlToken = payload.token;
  session.controlTargetId = payload.target_id;
  $("#remoteControlBar").hidden = false;
  $("#remoteScreenStage").classList.add("control-enabled");
  setScreenViewerStatus("Ao vivo · controle ativo · toque ou arraste sobre a tela");
  toast("Controle remoto autorizado para esta sessão.");
}

function sendControlEvent(event) {
  const session = state.screenSession;
  if (!session?.controlToken || state.ws?.readyState !== WebSocket.OPEN) return false;
  state.ws.send(JSON.stringify({
    type: "control_input", payload: {
      session_id: session.id, token: session.controlToken, event,
    }
  }));
  return true;
}

function remoteVideoPoint(pointerEvent) {
  const video = $("#remoteScreen");
  if (!video.videoWidth || !video.videoHeight) return null;
  const bounds = video.getBoundingClientRect();
  const scale = Math.min(bounds.width / video.videoWidth, bounds.height / video.videoHeight);
  const renderedWidth = video.videoWidth * scale;
  const renderedHeight = video.videoHeight * scale;
  const left = bounds.left + (bounds.width - renderedWidth) / 2;
  const top = bounds.top + (bounds.height - renderedHeight) / 2;
  const x = (pointerEvent.clientX - left) / renderedWidth;
  const y = (pointerEvent.clientY - top) / renderedHeight;
  if (x < 0 || x > 1 || y < 0 || y > 1) return null;
  return { x, y };
}

let activeControlPointer = null;
let lastControlMoveAt = 0;
let lastControlPoint = null;
let activeControlButton = "left";
let rightClickArmed = false;

function setRightClickArmed(enabled) {
  rightClickArmed = enabled;
  const button = $("#remoteRightClick");
  if (!button) return;
  button.setAttribute("aria-pressed", String(enabled));
  button.textContent = enabled ? "Toque…" : "Direito";
}

function startRemotePointer(event) {
  if (!state.screenSession?.controlToken) return;
  const point = remoteVideoPoint(event);
  if (!point) return;
  event.preventDefault();
  activeControlPointer = event.pointerId;
  event.currentTarget.setPointerCapture?.(event.pointerId);
  activeControlButton = rightClickArmed || event.button === 2 ? "right" : "left";
  lastControlPoint = point;
  sendControlEvent({ type: "move", ...point, button: activeControlButton });
  sendControlEvent({ type: "down", ...point, button: activeControlButton });
}

function moveRemotePointer(event) {
  if (activeControlPointer !== event.pointerId || !state.screenSession?.controlToken) return;
  const now = performance.now();
  if (now - lastControlMoveAt < 35) return;
  const point = remoteVideoPoint(event);
  if (!point) return;
  event.preventDefault();
  lastControlMoveAt = now;
  lastControlPoint = point;
  sendControlEvent({ type: "move", ...point, button: activeControlButton });
}

function endRemotePointer(event) {
  if (activeControlPointer !== event.pointerId) return;
  const point = remoteVideoPoint(event) || lastControlPoint;
  event.preventDefault();
  if (point) sendControlEvent({ type: "up", ...point, button: activeControlButton });
  if (rightClickArmed) {
    setRightClickArmed(false);
    setScreenViewerStatus("Ao vivo · controle ativo · toque ou arraste sobre a tela");
  }
  activeControlPointer = null;
  lastControlPoint = null;
}

async function showRemoteScreenFullscreen() {
  const stage = $("#screenViewerDialog .screen-dialog-content");
  try {
    if (!document.fullscreenElement) {
      await stage.requestFullscreen();
      const orientationLock = screen.orientation?.lock?.("landscape");
      if (orientationLock?.catch) await orientationLock.catch(() => { });
    } else {
      await document.exitFullscreen();
    }
  } catch {
    toast("Não foi possível entrar em tela cheia neste navegador.", true);
  }
}

function createScreenPeer(session) {
  if (!window.RTCPeerConnection) throw new Error("WebRTC não está disponível neste navegador.");
  const peer = new RTCPeerConnection({ iceServers: [] });
  session.peer = peer;
  peer.onicecandidate = event => {
    if (!event.candidate || state.screenSession !== session) return;
    sendScreenSignal(session.remoteDeviceId, "ice", { session_id: session.id, candidate: event.candidate.toJSON() }).catch(error => toast(error.message, true));
  };
  peer.onconnectionstatechange = () => {
    if (state.screenSession !== session) return;
    if (peer.connectionState === "connected") {
      if (session.role === "viewer") {
        setScreenViewerStatus(session.controlToken
          ? "Ao vivo · controle ativo · toque ou arraste sobre a tela"
          : "Ao vivo · conexão direta · use Tela cheia para ampliar");
        $("#screenViewerPlaceholder").hidden = true;
      } else {
        $("#screenBroadcastTitle").textContent = `Compartilhando com ${screenDeviceName(session.remoteDeviceId)}`;
      }
    }
    if (peer.connectionState === "failed") {
      toast("A conexão de tela falhou. Confira se os aparelhos continuam na mesma rede.", true);
      disposeScreenSession({ notifyPeer: true, reason: "A conexão WebRTC falhou." });
    }
  };
  if (session.role === "viewer") {
    peer.ontrack = event => {
      if (state.screenSession !== session) return;
      $("#remoteScreen").srcObject = event.streams[0] || new MediaStream([event.track]);
      $("#screenViewerPlaceholder").hidden = true;
      setScreenViewerStatus("Recebendo vídeo…");
    };
  }
  return peer;
}

async function flushScreenCandidates(session) {
  if (!session.peer?.remoteDescription) return;
  for (const candidate of session.pendingCandidates.splice(0)) await session.peer.addIceCandidate(candidate);
}

async function handleWebRtcSignal(signal) {
  const sessionId = signal.payload?.session_id;
  const session = state.screenSession;
  if (!session || session.id !== sessionId) return;
  if (signal.kind === "handoff" && session.role === "viewer") {
    if (session.remoteDeviceId !== signal.payload.previous_target_id) return;
    session.remoteDeviceId = signal.source_id;
    $("#screenViewerTitle").textContent = `Tela de ${screenDeviceName(signal.source_id)}`;
    setScreenViewerStatus("Notificação aberta. Aguardando aprovação da captura.");
    return;
  }
  if (session.remoteDeviceId !== signal.source_id) return;
  try {
    if (signal.kind === "decline") {
      const reason = signal.payload.reason || "O outro aparelho recusou a solicitação.";
      disposeScreenSession();
      toast(reason, true);
      return;
    }
    if (signal.kind === "end") {
      disposeScreenSession();
      toast(signal.payload.reason || "Compartilhamento encerrado.");
      return;
    }
    if (signal.kind === "ice") {
      if (session.peer?.remoteDescription) await session.peer.addIceCandidate(signal.payload.candidate);
      else session.pendingCandidates.push(signal.payload.candidate);
      return;
    }
    if (signal.kind === "offer" && session.role === "viewer") {
      const peer = session.peer || createScreenPeer(session);
      await peer.setRemoteDescription(signal.payload.description);
      await flushScreenCandidates(session);
      const answer = await peer.createAnswer();
      await peer.setLocalDescription(answer);
      await sendScreenSignal(session.remoteDeviceId, "answer", { session_id: session.id, description: peer.localDescription });
      setScreenViewerStatus("Conectando o vídeo…");
      return;
    }
    if (signal.kind === "answer" && session.role === "sharer") {
      await session.peer.setRemoteDescription(signal.payload.description);
      await flushScreenCandidates(session);
    }
  } catch (error) {
    toast(`Não foi possível negociar a tela: ${error.message}`, true);
    disposeScreenSession({ notifyPeer: true, reason: "Falha ao negociar a conexão." });
  }
}

function queueScreenConsent(command) {
  const sessionId = command.arguments?.session_id;
  if (!sessionId || command.arguments?.viewer_id !== command.actor_id) {
    return { status: "failed", detail: "Solicitação de tela inválida." };
  }
  if (!screenSharingSupported()) {
    sendScreenSignal(command.actor_id, "decline", { session_id: sessionId, reason: "O navegador de destino não oferece captura de tela." }).catch(() => { });
    return { status: "unsupported", detail: "Abra o Bridge no computador por http://127.0.0.1:8876." };
  }
  if (state.screenSession || state.pendingScreenCommand) {
    sendScreenSignal(command.actor_id, "decline", { session_id: sessionId, reason: "Este aparelho já está em outra sessão de tela." }).catch(() => { });
    return { status: "denied", detail: "Já existe uma sessão de tela em andamento." };
  }
  state.pendingScreenCommand = command;
  $("#screenRequester").textContent = screenDeviceName(command.actor_id);
  const canControl = Boolean(command.arguments?.control_target_id);
  $("#remoteControlConsent").hidden = !canControl;
  $("#allowRemoteControl").checked = false;
  $("#acceptScreenShare").disabled = false;
  const dialog = $("#screenConsentDialog");
  if (!dialog.open) dialog.showModal();
  toast("Uma solicitação de tela aguarda sua aprovação neste aparelho.");
  return { status: "needs_local_consent", detail: "Aguardando clique local e seletor do sistema." };
}

async function declineScreenShare(reason = "O compartilhamento foi recusado no aparelho de destino.") {
  const command = state.pendingScreenCommand;
  state.pendingScreenCommand = null;
  closeDialog("#screenConsentDialog");
  if (!command) return;
  await sendScreenSignal(command.actor_id, "decline", { session_id: command.arguments.session_id, reason }).catch(() => { });
  sendCommandResult(command, "denied", reason);
}

async function acceptScreenShare() {
  const command = state.pendingScreenCommand;
  if (!command) return;
  const button = $("#acceptScreenShare");
  button.disabled = true;
  let stream = null;
  try {
    let allowRemoteControl = !$("#remoteControlConsent").hidden && $("#allowRemoteControl").checked;
    stream = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: { ideal: 15, max: 30 } }, audio: false });
    const displaySurface = stream.getVideoTracks()[0]?.getSettings?.().displaySurface;
    if (allowRemoteControl && displaySurface && displaySurface !== "monitor") {
      allowRemoteControl = false;
      toast("A tela será transmitida sem controle. Para controlar o PC, escolha Tela inteira no seletor.", true);
    }
    state.pendingScreenCommand = null;
    closeDialog("#screenConsentDialog");
    const session = {
      id: command.arguments.session_id, role: "sharer", remoteDeviceId: command.actor_id,
      peer: null, stream, pendingCandidates: [], timeout: null,
    };
    state.screenSession = session;
    $("#localScreen").srcObject = stream;
    $("#screenBroadcastTitle").textContent = `Preparando tela para ${screenDeviceName(session.remoteDeviceId)}`;
    $("#screenBroadcastDialog").showModal();
    const peer = createScreenPeer(session);
    stream.getTracks().forEach(track => peer.addTrack(track, stream));
    stream.getVideoTracks()[0]?.addEventListener("ended", () => {
      if (state.screenSession === session) disposeScreenSession({ notifyPeer: true, reason: "O compartilhamento foi encerrado no aparelho de origem." });
    });
    const offer = await peer.createOffer();
    await peer.setLocalDescription(offer);
    await sendScreenSignal(session.remoteDeviceId, "offer", { session_id: session.id, description: peer.localDescription });
    if (allowRemoteControl) {
      try {
        await api(`/control-sessions/${encodeURIComponent(session.id)}/approve`, { method: "POST" });
      } catch (error) {
        toast(`A tela foi compartilhada, mas o controle não foi liberado: ${error.message}`, true);
      }
    }
    sendCommandResult(command, "completed", "Compartilhamento aprovado localmente.");
  } catch (error) {
    stream?.getTracks().forEach(track => track.stop());
    state.pendingScreenCommand = null;
    closeDialog("#screenConsentDialog");
    await sendScreenSignal(command.actor_id, "decline", { session_id: command.arguments.session_id, reason: "A captura não foi aprovada no aparelho de destino." }).catch(() => { });
    sendCommandResult(command, "denied", error.message);
    toast(error.name === "NotAllowedError" ? "Compartilhamento cancelado." : error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function requestScreen(targetId) {
  const target = state.devices.find(device => device.id === targetId);
  if (!target || target.id === state.deviceId) throw new Error("Escolha outro aparelho.");
  if (!["web", "windows"].includes(target.device_type)) throw new Error("A captura de tela ainda não está disponível para este tipo de aparelho.");
  if (!window.RTCPeerConnection) throw new Error("Este navegador não oferece WebRTC.");
  if (state.screenSession) disposeScreenSession({ notifyPeer: true });
  const session = {
    id: randomUuid(), role: "viewer", remoteDeviceId: targetId,
    peer: null, stream: null, pendingCandidates: [], timeout: null, controlToken: null, controlTargetId: null,
  };
  state.screenSession = session;
  showScreenViewer(session);
  try {
    const challenge = await api("/commands/confirm", { method: "POST", body: JSON.stringify({ actor_id: state.deviceId, target_id: targetId, action: "screen_start" }) });
    const result = await api("/commands", {
      method: "POST", body: JSON.stringify({
        actor_id: state.deviceId, target_id: targetId, action: "screen_start",
        arguments: { session_id: session.id, viewer_id: state.deviceId }, confirmation_token: challenge.confirmation_token,
      })
    });
    if (!result.delivered_live) throw new Error("O painel do aparelho de destino precisa estar aberto.");
    session.timeout = setTimeout(() => {
      if (state.screenSession === session && !session.peer) {
        disposeScreenSession({ notifyPeer: true, reason: "A solicitação expirou." });
        toast("A solicitação de tela expirou sem aprovação.", true);
      }
    }, SCREEN_REQUEST_TIMEOUT_MS);
  } catch (error) {
    if (state.screenSession === session) disposeScreenSession();
    throw error;
  }
}

async function claimScreenHandoffFromUrl() {
  const params = new URLSearchParams(location.search);
  const commandId = params.get("screen_request");
  if (!commandId) return;
  params.delete("screen_request");
  const cleanQuery = params.toString();
  history.replaceState({}, "", `${location.pathname}${cleanQuery ? `?${cleanQuery}` : ""}${location.hash}`);
  try {
    const result = await api(`/screen-handoffs/${encodeURIComponent(commandId)}/claim`, { method: "POST" });
    handleBrowserCommand(result.command);
    toast("Solicitação recebida. Aprove a tela que deseja compartilhar.");
  } catch (error) {
    toast(error.message, true);
  }
}

function validatedRemoteUrl(value) {
  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol) || !url.hostname) throw new Error("Somente URLs HTTP ou HTTPS completas são permitidas.");
  if (url.username || url.password) throw new Error("URLs com usuário ou senha embutidos não são permitidas.");
  if (url.href.length > 2_048) throw new Error("O endereço é longo demais.");
  return url.href;
}

function queueRemoteUrl(command) {
  if (state.pendingUrlCommand) return { status: "denied", detail: "Já existe outro link aguardando decisão." };
  const url = validatedRemoteUrl(command.arguments?.url || "");
  state.pendingUrlCommand = { command, url };
  $("#urlRequester").textContent = screenDeviceName(command.actor_id);
  $("#remoteUrlPreview").textContent = url;
  const dialog = $("#urlConsentDialog");
  if (!dialog.open) dialog.showModal();
  toast("Um link recebido aguarda sua aprovação.");
  return { status: "needs_local_consent", detail: "Aguardando abertura em nova guia." };
}

function declineRemoteUrl() {
  const pending = state.pendingUrlCommand;
  state.pendingUrlCommand = null;
  closeDialog("#urlConsentDialog");
  if (pending) sendCommandResult(pending.command, "denied", "O link não foi aberto no aparelho de destino.");
}

function acceptRemoteUrl() {
  const pending = state.pendingUrlCommand;
  if (!pending) return;
  try {
    const opened = window.open("about:blank", "_blank");
    if (!opened) throw new Error("O navegador bloqueou a nova guia. Permita pop-ups para o Bridge e tente novamente.");
    opened.opener = null;
    opened.location.replace(pending.url);
    sendCommandResult(pending.command, "completed", "Link aberto em nova guia.");
    state.pendingUrlCommand = null;
    closeDialog("#urlConsentDialog");
    toast("Link aberto em uma nova guia. O Bridge continua conectado.");
  } catch (error) {
    sendCommandResult(pending.command, "failed", error.message);
    toast(error.message, true);
  }
}

async function handleBrowserCommand(command) {
  let status = "completed", detail = "";
  try {
    if (command.action === "ring") { for (let i = 0; i < 3; i++) { navigator.vibrate?.([180, 100]); } toast("Este aparelho está tocando para ser localizado."); }
    else if (command.action === "notify") toast(command.arguments.message || "Notificação do Bridge");
    else if (command.action === "open_url") ({ status, detail } = queueRemoteUrl(command));
    else if (command.action === "screen_start") ({ status, detail } = queueScreenConsent(command));
    else if (command.action === "screen_stop") disposeScreenSession();
    else if (command.action === "lock") { status = "unsupported"; detail = "Navegadores não podem bloquear o sistema operacional."; }
    else { status = "unsupported"; detail = "Ação destinada ao agente nativo."; }
  } catch (error) { status = "failed"; detail = error.message; }
  sendCommandResult(command, status, detail);
}

async function sendMessage(event) {
  event.preventDefault();
  if (!$("#messageTarget").value) return toast("Pareie outro aparelho primeiro.", true);
  try {
    const result = await api("/messages", { method: "POST", body: JSON.stringify({ kind: $("#messageKind").value, source_id: state.deviceId, target_id: $("#messageTarget").value, content: $("#messageContent").value, behavior: $("#messageBehavior").value }) });
    $("#messageContent").value = ""; toast(result.delivered_live ? "Entregue ao vivo." : "Guardado para o aparelho de destino."); addFeed(result.kind, result);
  } catch (error) { toast(error.message, true); }
}

async function sha256(file) {
  if (file.size > 100 * 1024 * 1024) return null;
  // Web Crypto is intentionally unavailable in browsers opened through a
  // plain-HTTP LAN address (for example, http://192.168.x.x). In that case the
  // Core still calculates and records SHA-256 after receiving every byte.
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return null;
  const digest = await subtle.digest("SHA-256", await file.arrayBuffer());
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, "0")).join("");
}

function safeFileName(file) {
  return (file.webkitRelativePath || file.name).replaceAll("/", "__").replaceAll("\\", "__");
}

function transferById(transferId) {
  return state.transfers.find(item => item.id === transferId);
}

function updateTransfer(updated) {
  const current = transferById(updated.id);
  if (!current) {
    state.transfers.unshift(updated);
    renderTransfers();
    return updated;
  }
  const previousStatus = current.status;
  Object.assign(current, updated);
  if (current.status !== previousStatus) renderTransfers();
  else updateTransferProgress(current);
  return current;
}

function updateTransferProgress(transfer) {
  const row = document.querySelector(`[data-transfer-id="${transfer.id}"]`);
  if (!row) return renderTransfers();
  const progress = transfer.total_size ? Math.round(transfer.received_size / transfer.total_size * 100) : 0;
  const summary = row.querySelector("[data-transfer-summary]");
  const bar = row.querySelector("[data-transfer-progress]");
  if (summary) summary.textContent = `${STATUS_LABELS[transfer.status] || transfer.status} · ${progress}%`;
  if (bar) bar.style.width = `${progress}%`;
}

async function continueUpload(transferId) {
  const context = state.uploads.get(transferId);
  if (!context || context.running) return context?.promise;
  context.running = true;
  context.promise = (async () => {
    const chunkSize = 1024 * 1024;
    while (true) {
      const transfer = transferById(transferId);
      if (!transfer || context.paused || ["paused", "cancelled", "completed", "integrity_failed"].includes(transfer.status)) return;
      const offset = Number(transfer.received_size || 0);
      if (offset >= context.file.size) return;
      const chunk = context.file.slice(offset, Math.min(offset + chunkSize, context.file.size));
      try {
        const updated = await api(`/transfers/${transferId}/chunks`, {
          method: "PUT", headers: { "X-Offset": String(offset), "Content-Type": "application/octet-stream" }, body: chunk,
        });
        updateTransfer(updated);
        if (updated.status === "completed") {
          if (!context.completedToast) toast(`${updated.file_name} foi enviado diretamente.`);
          context.completedToast = true;
          return;
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          await loadTransfers();
          const fresh = transferById(transferId);
          if (context.paused || fresh?.status === "paused") return;
          if (error.detail?.expected_offset != null && fresh) {
            fresh.received_size = Number(error.detail.expected_offset);
            continue;
          }
        }
        throw error;
      }
    }
  })().catch(error => toast(`${context.file.name}: ${error.message}`, true)).finally(() => {
    context.running = false;
  });
  return context.promise;
}

async function uploadFile(file) {
  const target = $("#fileTarget").value;
  if (!target) return toast("Adicione e selecione um aparelho de destino.", true);
  const safeName = safeFileName(file);
  try {
    toast(`Preparando ${safeName}...`);
    const transfer = await api("/transfers", { method: "POST", body: JSON.stringify({ source_id: state.deviceId, target_id: target, file_name: safeName, total_size: file.size, sha256: await sha256(file) }) });
    state.transfers.unshift(transfer); renderTransfers();
    state.uploads.set(transfer.id, { file, paused: false, running: false, promise: null, completedToast: false });
    if (file.size === 0) toast("Arquivo vazio entregue.");
    else await continueUpload(transfer.id);
  } catch (error) { toast(`${safeName}: ${error.message}`, true); }
}

async function handleFiles(files) { for (const file of files) await uploadFile(file); }

function downloadReceivedTransfer(transfer) {
  const link = document.createElement("a");
  link.href = `/api/transfers/${transfer.id}/download`;
  link.download = transfer.file_name || "arquivo";
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  toast(`${transfer.file_name || "Arquivo"} recebido. O download começou automaticamente.`);
}

function renderTransfers() {
  $("#transferQueue").innerHTML = state.transfers.slice(0, 8).map(transfer => {
    const progress = transfer.total_size ? Math.round(transfer.received_size / transfer.total_size * 100) : 0;
    const otherId = transfer.source_id === state.deviceId ? transfer.target_id : transfer.source_id;
    const other = state.devices.find(device => device.id === otherId)?.name || "aparelho";
    const direction = transfer.source_id === state.deviceId ? `Para ${other}` : `De ${other}`;
    const isSender = transfer.source_id === state.deviceId;
    return `<div class="transfer" data-transfer-id="${transfer.id}"><div class="transfer-head"><div><strong>${escapeHtml(transfer.file_name)}</strong><small>${escapeHtml(direction)}</small></div><span data-transfer-summary>${escapeHtml(STATUS_LABELS[transfer.status] || transfer.status)} · ${progress}%</span></div><div class="progress"><span data-transfer-progress style="width:${progress}%"></span></div><div class="device-actions">${isSender && ["accepted", "receiving"].includes(transfer.status) ? `<button class="button ghost" data-transfer-action="pause" data-id="${transfer.id}">Pausar</button>` : ""}${isSender && transfer.status === "paused" ? `<button class="button secondary" data-transfer-action="resume" data-id="${transfer.id}">Retomar</button>` : ""}${transfer.status === "completed" && transfer.target_id === state.deviceId ? `<a class="button secondary" href="/api/transfers/${transfer.id}/download" download>Baixar novamente</a>` : ""}</div></div>`;
  }).join("");
  $$("[data-transfer-action]").forEach(button => button.onclick = () => changeTransferState(button.dataset.id, button.dataset.transferAction));
}

async function loadTransfers() { if (!state.deviceId) return; state.transfers = await api(`/transfers?device_id=${state.deviceId}`); renderTransfers(); }

async function changeTransferState(transferId, action) {
  const context = state.uploads.get(transferId);
  if (action === "resume" && !context?.file) {
    state.resumeTransferId = transferId;
    $("#resumeFileInput").click();
    return;
  }
  if (action === "pause" && context) context.paused = true;
  if (action === "resume" && context?.running) await context.promise;
  try {
    const updated = await api(`/transfers/${transferId}/${action}`, { method: "POST" });
    updateTransfer(updated);
    if (action === "resume" && context) {
      context.paused = false;
      continueUpload(transferId);
    }
  } catch (error) {
    if (action === "pause" && context) {
      context.paused = false;
      continueUpload(transferId);
    }
    toast(error.message, true);
  }
}

async function resumeWithFile(transferId, file) {
  const transfer = transferById(transferId);
  if (!transfer) return toast("Transferência não encontrada.", true);
  if (safeFileName(file) !== transfer.file_name || file.size !== transfer.total_size) {
    return toast("Escolha o mesmo arquivo usado no início da transferência.", true);
  }
  if (transfer.sha256_expected) {
    const digest = await sha256(file);
    if (digest && digest.toLowerCase() !== transfer.sha256_expected.toLowerCase()) {
      return toast("O arquivo escolhido não é o mesmo do envio original.", true);
    }
  }
  state.uploads.set(transferId, { file, paused: true, running: false, promise: null, completedToast: false });
  await changeTransferState(transferId, "resume");
}

function deviceName(deviceId, fallback) {
  if (!deviceId) return fallback;
  return state.devices.find(device => device.id === deviceId)?.name || fallback;
}

function eventDescription(item) {
  const payload = item.payload || {};
  const source = item.source_name || deviceName(item.source_id, "um aparelho removido");
  const target = item.target_name || deviceName(item.target_id, "outro aparelho removido");
  const transfer = state.transfers.find(entry => entry.id === payload.transfer_id);
  const fileName = payload.file_name || item.file_name || transfer?.file_name || "arquivo";
  const action = ACTION_LABELS[payload.action] || humanKind(payload.action || "ação").toLowerCase();
  const descriptions = {
    pairing_requested: `${payload.name || source} iniciou o cadastro.`,
    pairing_confirmed: `${source} foi adicionado ao Bridge.`,
    pairing_failed: "Uma tentativa de cadastro não foi aceita.",
    device_revoked: `${source} foi removido do Bridge.`,
    permissions_changed: `As permissões de ${target} foram atualizadas.`,
    transfer_offered: `${source} começou a enviar ${fileName} para ${target}.`,
    transfer_completed: `${fileName} chegou a ${target} e foi verificado.`,
    transfer_pause: `O envio de ${fileName} foi pausado.`,
    transfer_resume: `O envio de ${fileName} foi retomado.`,
    transfer_cancel: `O envio de ${fileName} foi cancelado.`,
    integrity_failed: `${fileName} não passou na verificação de integridade.`,
    text: `${source} enviou um texto para ${target}.`, snippet: `${source} enviou um trecho para ${target}.`,
    link: `${source} enviou um link para ${target}.`, clipboard: `${source} enviou o clipboard para ${target}.`,
    photo_offer: `${source} ofereceu uma foto para ${target}.`,
    command_issued: `${source} enviou a ação “${action}” para ${target}.`,
    command_result: `${source} concluiu a ação “${action}”.`,
    command_denied: `A ação “${action}” para ${target} foi recusada.`,
    sensitive_action_challenge: `${source} confirmou uma ação sensível para ${target}.`,
    file_requested: `${source} pediu um arquivo a ${target}.`,
    team_member_changed: `${target} teve sua participação em equipe atualizada.`,
    notification_action: `${source} respondeu a uma notificação.`,
    p2p_signal: `${source} negociou uma conexão direta com ${target}.`,
    rule_applied: `Uma automação de ${source} foi executada.`,
    drive2_queued: `${fileName} foi preparado para arquivamento.`,
  };
  return descriptions[item.kind] || "Evento registrado pelo Bridge.";
}

async function loadHistory() {
  try {
    const items = await api(`/history?limit=150&security_only=${$("#securityOnly").checked}`);
    $("#historyList").innerHTML = items.map(item => `<article class="timeline-item"><span class="timeline-icon">${item.security ? "⌾" : "◇"}</span><div class="timeline-content"><strong>${escapeHtml(EVENT_LABELS[item.kind] || humanKind(item.kind))}</strong><small> · ${escapeHtml(STATUS_LABELS[item.status] || item.status)} · ${formatTime(item.created_at)}</small><p>${escapeHtml(eventDescription(item))}</p></div>${!item.security ? `<button class="button ghost" data-delete-event="${item.id}">Limpar</button>` : ""}</article>`).join("") || `<div class="feed empty">Histórico vazio.</div>`;
    $$("[data-delete-event]").forEach(button => button.onclick = async () => { await api(`/history/${button.dataset.deleteEvent}`, { method: "DELETE" }); loadHistory(); });
  } catch (error) { toast(error.message, true); }
}

async function loadNetwork() {
  try {
    const [identity, discovery] = await Promise.all([api("/system/identity"), api("/discovery")]);
    $("#localAddress").textContent = identity.url; $("#fingerprint").textContent = identity.fingerprint;
    $("#peerCount").textContent = `${discovery.peers.length} outro(s) Bridge detectado(s) na LAN`;
  } catch (error) { toast(error.message, true); }
}

function openActions(deviceId) {
  const device = state.devices.find(item => item.id === deviceId); if (!device) return;
  $("#actionTitle").textContent = device.name;
  const actions = [["ring", "Tocar som"], ["request_file", "Pedir arquivo"]];
  const canCaptureScreen = device.device_type === "windows" || device.capabilities?.screen_capture !== false;
  if (device.id !== state.deviceId && ["web", "windows"].includes(device.device_type) && canCaptureScreen) {
    actions.push(["screen_start", device.device_type === "windows" ? "Pedir tela por notificação" : "Ver tela"]);
  }
  actions.push(["lock", "Bloquear"], ["open_url", "Abrir URL"], ["revoke", "Revogar"]);
  const screenNote = device.id !== state.deviceId && device.device_type === "windows"
    ? `<p class="action-note">O agente mostrará uma notificação. Ao clicar em “Abrir Bridge”, o navegador pedirá qual tela compartilhar.</p>`
    : device.id !== state.deviceId && device.device_type === "web" && device.capabilities?.screen_capture === false
      ? `<p class="action-note">Este navegador pode assistir telas, mas não consegue capturar a própria tela. Para ver o celular no computador será necessário o app Android nativo.</p>`
      : device.id !== state.deviceId && device.device_type !== "web"
        ? `<p class="action-note">A transmissão de tela nativa ainda não está disponível para este tipo de aparelho.</p>` : "";
  $("#actionBody").innerHTML = actions.map(([action, label]) => `<button class="button ${["lock", "revoke"].includes(action) ? "danger" : "secondary"}" data-command="${action}" data-target="${deviceId}">${label}</button>`).join("") + screenNote;
  $$("[data-command]").forEach(button => button.onclick = () => performAction(button.dataset.command, button.dataset.target));
  $("#actionDialog").showModal();
}

async function performAction(action, targetId) {
  const actionKey = `${targetId}:${action}`;
  if (state.pendingActions.has(actionKey)) return toast("Esta ação já está sendo enviada.");
  const button = $(`[data-command="${action}"][data-target="${targetId}"]`);
  const previousLabel = button?.textContent;
  state.pendingActions.add(actionKey);
  if (button) { button.disabled = true; button.textContent = "Enviando…"; }
  try {
    if (action === "revoke") { if (!confirm("Revogar este aparelho imediatamente?")) return; await api(`/devices/${targetId}`, { method: "DELETE" }); $("#actionDialog").close(); return loadDevices(); }
    if (action === "request_file") { await api("/file-requests", { method: "POST", body: JSON.stringify({ requester_id: state.deviceId, target_id: targetId, note: "Escolha um arquivo para compartilhar comigo" }) }); }
    else {
      if (action === "screen_start") {
        if (!confirm("Solicitar a tela deste aparelho? A outra pessoa ainda precisará aprovar localmente e escolher o que compartilhar.")) return;
        $("#actionDialog").close();
        await requestScreen(targetId);
        toast("Solicitação enviada. Aprove o compartilhamento no outro aparelho.");
        return;
      }
      if (action === "open_url") {
        state.urlTarget = targetId;
        $("#actionDialog").close();
        $("#urlDialog").showModal();
        $("#urlInput").focus();
        return;
      }
      let token = null;
      if (action === "lock") {
        if (!confirm(`Confirmar ação sensível: ${action}? Ela será registrada no log de segurança.`)) return;
        const challenge = await api("/commands/confirm", { method: "POST", body: JSON.stringify({ actor_id: state.deviceId, target_id: targetId, action }) }); token = challenge.confirmation_token;
      }
      await api("/commands", { method: "POST", body: JSON.stringify({ actor_id: state.deviceId, target_id: targetId, action, arguments: {}, confirmation_token: token }) });
    }
    $("#actionDialog").close(); toast("Solicitação enviada e registrada.");
  } catch (error) { toast(error.message, true); }
  finally {
    setTimeout(() => {
      state.pendingActions.delete(actionKey);
      if (button?.isConnected) { button.disabled = false; button.textContent = previousLabel; }
    }, 1_200);
  }
}

async function sendUrlCommand(event) {
  event.preventDefault();
  try {
    const url = validatedRemoteUrl($("#urlInput").value);
    const result = await api("/commands", { method: "POST", body: JSON.stringify({ actor_id: state.deviceId, target_id: state.urlTarget, action: "open_url", arguments: { url }, confirmation_token: null }) });
    $("#urlDialog").close();
    $("#urlInput").value = "";
    toast(result.delivered_live
      ? "Link enviado. Confirme no outro aparelho para abrir em uma nova guia."
      : "O painel do outro aparelho está fechado; o link não foi aberto.", !result.delivered_live);
  } catch (error) { toast(error.message, true); }
}

async function refreshAll() {
  await loadDevices();
  await loadTransfers();
  await loadRecentActivity();
}

function bindEvents() {
  $("#pairNew").onclick = () => { location.hash = "settings"; };
  $("#requestPair").onclick = requestPair;
  $("#pairForm").onsubmit = confirmPair;
  $("#restartPair").onclick = resetPairDialog;
  $("#messageForm").onsubmit = sendMessage;
  $("#urlForm").onsubmit = sendUrlCommand;
  $("#acceptRemoteUrl").onclick = acceptRemoteUrl;
  $("#declineRemoteUrl").onclick = declineRemoteUrl;
  $("#screenSharePermission").onchange = updateScreenPermission;
  $("#acceptScreenShare").onclick = acceptScreenShare;
  $("#declineScreenShare").onclick = () => declineScreenShare();
  $("#stopScreenViewing").onclick = () => disposeScreenSession({ notifyPeer: true, reason: "A visualização foi encerrada." });
  $("#fullscreenRemoteScreen").onclick = showRemoteScreenFullscreen;
  $("#remoteScrollUp").onclick = () => sendControlEvent({ type: "scroll", delta: 1 });
  $("#remoteScrollDown").onclick = () => sendControlEvent({ type: "scroll", delta: -1 });
  $("#remoteRightClick").onclick = () => {
    if (!state.screenSession?.controlToken) return;
    setRightClickArmed(!rightClickArmed);
    setScreenViewerStatus(rightClickArmed
      ? "Clique direito armado · toque no ponto desejado"
      : "Ao vivo · controle ativo · toque ou arraste sobre a tela");
  };
  $("#remoteEnter").onclick = () => sendControlEvent({ type: "key", key: "ENTER" });
  $("#remoteTypeText").onclick = () => {
    const text = prompt("Texto para digitar no computador:");
    if (text) sendControlEvent({ type: "text", text: text.slice(0, 500) });
  };
  $("#remoteScreenStage").addEventListener("pointerdown", startRemotePointer);
  $("#remoteScreenStage").addEventListener("pointermove", moveRemotePointer);
  $("#remoteScreenStage").addEventListener("pointerup", endRemotePointer);
  $("#remoteScreenStage").addEventListener("pointercancel", endRemotePointer);
  $("#remoteScreenStage").addEventListener("contextmenu", event => {
    if (state.screenSession?.controlToken) event.preventDefault();
  });
  $("#stopScreenBroadcast").onclick = () => disposeScreenSession({ notifyPeer: true, reason: "O compartilhamento foi encerrado no aparelho de origem." });
  $("#securityOnly").onchange = loadHistory;
  $("#chooseFile").onclick = event => { event.stopPropagation(); $("#fileInput").click(); };
  $("#chooseFolder").onclick = event => { event.stopPropagation(); $("#directoryInput").click(); };
  $("#fileInput").onchange = event => { handleFiles(event.target.files); event.target.value = ""; };
  $("#directoryInput").onchange = event => { handleFiles(event.target.files); event.target.value = ""; };
  $("#resumeFileInput").onchange = event => {
    const file = event.target.files[0];
    const transferId = state.resumeTransferId;
    event.target.value = "";
    state.resumeTransferId = null;
    if (file && transferId) resumeWithFile(transferId, file).catch(error => toast(error.message, true));
  };
  const zone = $("#dropZone"); zone.onclick = event => { if (!event.target.closest("button")) $("#fileInput").click(); };
  zone.onkeydown = event => { if (["Enter", " "].includes(event.key)) $("#fileInput").click(); };
  for (const type of ["dragenter", "dragover"]) zone.addEventListener(type, event => { event.preventDefault(); zone.classList.add("dragging"); });
  for (const type of ["dragleave", "drop"]) zone.addEventListener(type, event => { event.preventDefault(); zone.classList.remove("dragging"); });
  zone.ondrop = event => handleFiles(event.dataTransfer.files);
  $$('[data-close]').forEach(button => button.onclick = () => {
    const dialog = button.closest("dialog");
    dialog.close();
    if (dialog.id === "pairDialog") resetPairDialog();
  });
  window.addEventListener("beforeinstallprompt", event => { event.preventDefault(); state.installPrompt = event; $("#installButton").hidden = false; });
  window.addEventListener("beforeunload", () => disposeScreenSession());
  $("#installButton").onclick = async () => { await state.installPrompt?.prompt(); $("#installButton").hidden = true; };
}

async function init() {
  bindEvents();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js?v=17").then(registration => registration.update()).catch(() => { });
  try {
    await ensureIdentity();
    if (state.deviceId) { connectSocket(); await refreshAll(); await claimScreenHandoffFromUrl(); }
    route();
  }
  catch (error) { setConnection("offline", "Core indisponível"); toast(error.message, true); }
}
init();
