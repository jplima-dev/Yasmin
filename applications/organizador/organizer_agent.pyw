import asyncio
import json
import os
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

import websockets

HOST = "127.0.0.1"
VITE_PORT = 5173
WS_PORT = 8765
TARGET_URL = f"http://{HOST}:{VITE_PORT}/#/dashboard"
SHUTDOWN_DELAY = 180  # 3 minutos

# Coloque este arquivo na mesma pasta do package.json.
PROJECT_DIR = Path(__file__).resolve().parent
LOG_FILE = PROJECT_DIR / "organizer-agent.log"


async def port_open(port: int, timeout: float = 0.25) -> bool:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(HOST, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


class OrganizerAgent:
    def __init__(self):
        self.vite_process = None
        self.vite_log = None
        self.fallback_server = None
        self.start_lock = asyncio.Lock()
        self.app_clients = set()
        self.bootstrap_clients = set()
        self.shutdown_task = None

    def log(self, message: str):
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as file:
                file.write(message + "\n")
        except Exception:
            pass

    async def start_fallback(self):
        """Ocupa 5173 com uma página mínima quando o Vite está desligado."""
        if self.fallback_server is not None:
            return

        for _ in range(25):
            if await port_open(VITE_PORT):
                await asyncio.sleep(0.2)
                continue
            try:
                self.fallback_server = await asyncio.start_server(
                    self.handle_fallback_http, HOST, VITE_PORT
                )
                return
            except OSError:
                await asyncio.sleep(0.2)

        self.log("Não foi possível assumir a porta 5173.")

    async def stop_fallback(self):
        if self.fallback_server is None:
            return
        server = self.fallback_server
        self.fallback_server = None
        server.close()
        await server.wait_closed()

    async def handle_fallback_http(self, reader, writer):
        """Serve a tela 'Abrindo...' e dispara o npm na mesma guia."""
        try:
            try:
                await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=2)
            except Exception:
                pass

            body = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Abrindo Organizador...</title>
<style>
html,body{{height:100%;margin:0;font-family:system-ui,sans-serif;background:#111;color:#eee}}
body{{display:grid;place-items:center}}
main{{text-align:center;max-width:520px;padding:32px}}
.dot{{width:12px;height:12px;border-radius:50%;background:#eee;margin:18px auto;animation:pulse 1s infinite alternate}}
@keyframes pulse{{to{{opacity:.2;transform:scale(.7)}}}}
small{{opacity:.7}}
</style>
</head>
<body>
<main>
  <h1>Abrindo o Organizador…</h1>
  <div class="dot"></div>
  <small id="status">Iniciando o servidor local.</small>
</main>
<script>
(() => {{
  const status = document.getElementById("status");
  const target = {json.dumps(TARGET_URL)};
  let opened = false;

  function openApp() {{
    if (opened) return;
    opened = true;
    // O fallback e o app usam o mesmo endereço. Navegar para uma URL idêntica
    // pode ser ignorado pelo navegador; nesse caso é preciso buscar novamente
    // o documento, agora já servido pelo preview estável.
    if (location.href === target) location.reload();
    else location.replace(target);
  }}

  // A mensagem WebSocket acelera a abertura. A sondagem abaixo é a garantia:
  // cobre a pequena janela em que o servidor fica pronto antes de o cliente
  // terminar de se registrar no agente.
  async function waitUntilReady() {{
    if (opened) return;
    try {{
      const response = await fetch("/integration-status?ready=" + Date.now(), {{ cache: "no-store" }});
      if (response.ok) {{
        const data = await response.json();
        if (typeof data.available !== "boolean") throw new Error("not-ready");
        openApp();
        return;
      }}
    }} catch {{}}
    setTimeout(waitUntilReady, 400);
  }}

  function connect() {{
    const ws = new WebSocket("ws://{HOST}:{WS_PORT}");

    ws.addEventListener("open", () => {{
      ws.send(JSON.stringify({{type: "bootstrap"}}));
    }});

    ws.addEventListener("message", (event) => {{
      let data;
      try {{ data = JSON.parse(event.data); }} catch {{ return; }}

      if (data.type === "vite_ready") openApp();
      if (data.type === "vite_error")
        status.textContent = data.message || "Falha ao iniciar o Organizador.";
    }});

    ws.addEventListener("close", () => {{
      status.textContent = "Reconectando ao agente local…";
      setTimeout(connect, 1000);
    }});
  }}

  connect();
  waitUntilReady();
}})();
</script>
</body>
</html>""".encode("utf-8")

            headers = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html; charset=utf-8\r\n"
                b"Cache-Control: no-store\r\n"
                b"Connection: close\r\n"
                + f"Content-Length: {len(body)}\r\n\r\n".encode()
            )
            writer.write(headers + body)
            await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

        asyncio.create_task(self.ensure_vite())

    async def ensure_vite(self):
        async with self.start_lock:
            # Já é o servidor estável iniciado por este agente.
            if self.vite_process and self.vite_process.returncode is None:
                if await port_open(VITE_PORT):
                    await self.broadcast({"type": "vite_ready"})
                    return

            # 5173 já está ocupada por outro processo: não crie outro servidor.
            if self.fallback_server is None and await port_open(VITE_PORT):
                await self.broadcast({"type": "vite_ready"})
                return

            if not (PROJECT_DIR / "package.json").exists():
                await self.broadcast({
                    "type": "vite_error",
                    "message": f"package.json não encontrado em {PROJECT_DIR}"
                })
                return

            npm = "npm.cmd" if os.name == "nt" else "npm"
            creationflags = 0
            if os.name == "nt":
                creationflags = (
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    | subprocess.CREATE_NO_WINDOW
                )

            self.vite_log = open(LOG_FILE, "ab", buffering=0)
            try:
                # O atalho de uso normal serve o build, sem o cliente de HMR do
                # Vite. Assim, sincronizações do OneDrive e alterações na fonte
                # não recarregam uma página que a pessoa esteja usando.
                build_process = await asyncio.create_subprocess_exec(
                    npm,
                    "run",
                    "build",
                    cwd=str(PROJECT_DIR),
                    stdout=self.vite_log,
                    stderr=self.vite_log,
                    creationflags=creationflags,
                )
                build_code = await build_process.wait()
                if build_code != 0:
                    self.log(f"Build encerrado com código {build_code}.")
                    self.vite_log.close()
                    self.vite_log = None
                    await self.broadcast({
                        "type": "vite_error",
                        "message": f"Não foi possível preparar o Organizador. Veja {LOG_FILE.name}."
                    })
                    return

                # O fallback continua respondendo enquanto o build acontece e
                # só libera a porta imediatamente antes de iniciar o preview.
                await self.stop_fallback()
                self.vite_process = await asyncio.create_subprocess_exec(
                    npm,
                    "run",
                    "serve",
                    cwd=str(PROJECT_DIR),
                    stdout=self.vite_log,
                    stderr=self.vite_log,
                    creationflags=creationflags,
                )
            except Exception as exc:
                self.log(f"Falha ao iniciar npm: {exc}")
                if self.vite_log:
                    self.vite_log.close()
                self.vite_log = None
                self.vite_process = None
                await self.start_fallback()
                await self.broadcast({
                    "type": "vite_error",
                    "message": f"Falha ao iniciar a versão estável: {exc}"
                })
                return

            proc = self.vite_process
            log_handle = self.vite_log
            asyncio.create_task(self.watch_vite(proc, log_handle))

            # Só verifica durante a inicialização; NÃO é o detector de abas.
            for _ in range(150):  # ~30 s no máximo
                if proc.returncode is not None:
                    break
                if await port_open(VITE_PORT):
                    await self.broadcast({"type": "vite_ready"})
                    return
                await asyncio.sleep(0.2)

            await self.broadcast({
                "type": "vite_error",
                "message": f"O Organizador não abriu a porta {VITE_PORT}. Veja {LOG_FILE.name}."
            })

    async def watch_vite(self, proc, log_handle):
        code = await proc.wait()

        if log_handle:
            try:
                log_handle.close()
            except Exception:
                pass

        if self.vite_process is proc:
            self.vite_process = None
            self.vite_log = None

        self.log(f"Servidor do Organizador encerrado com código {code}.")
        await self.start_fallback()

    async def stop_vite(self):
        proc = self.vite_process
        if not proc or proc.returncode is not None:
            await self.start_fallback()
            return

        self.log("Nenhuma aba por 3 minutos. Encerrando o servidor do Organizador.")

        if os.name == "nt":
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/PID", str(proc.pid),
                "/T",
                "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            await killer.wait()
        else:
            proc.terminate()

        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()

        await self.start_fallback()

    async def delayed_shutdown(self):
        try:
            await asyncio.sleep(SHUTDOWN_DELAY)
            if not self.app_clients:
                await self.stop_vite()
        except asyncio.CancelledError:
            pass
        finally:
            if self.shutdown_task is asyncio.current_task():
                self.shutdown_task = None

    def cancel_shutdown(self):
        if self.shutdown_task and not self.shutdown_task.done():
            self.shutdown_task.cancel()
        self.shutdown_task = None

    def schedule_shutdown(self):
        if self.shutdown_task and not self.shutdown_task.done():
            return
        self.shutdown_task = asyncio.create_task(self.delayed_shutdown())

    async def ws_handler(self, websocket):
        is_app = False
        is_bootstrap = False

        try:
            async for raw in websocket:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                if msg_type == "app_open" and not is_app:
                    is_app = True
                    self.app_clients.add(websocket)
                    self.cancel_shutdown()
                    await websocket.send(json.dumps({"type": "registered"}))

                elif msg_type == "bootstrap" and not is_bootstrap:
                    is_bootstrap = True
                    self.bootstrap_clients.add(websocket)

                    if (
                        self.vite_process
                        and self.vite_process.returncode is None
                        and await port_open(VITE_PORT)
                    ):
                        await websocket.send(json.dumps({"type": "vite_ready"}))
                    else:
                        asyncio.create_task(self.ensure_vite())

        finally:
            if is_app:
                self.app_clients.discard(websocket)
                if not self.app_clients:
                    self.schedule_shutdown()

            if is_bootstrap:
                self.bootstrap_clients.discard(websocket)

    async def broadcast(self, payload):
        if not self.bootstrap_clients:
            return
        message = json.dumps(payload)
        await asyncio.gather(
            *(client.send(message) for client in list(self.bootstrap_clients)),
            return_exceptions=True,
        )


def port_is_open_sync(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((HOST, port)) == 0


async def run_agent(open_browser: bool):
    agent = OrganizerAgent()

    async with websockets.serve(agent.ws_handler, HOST, WS_PORT):
        # Quando o servidor do app está desligado, o agente assume 5173.
        if not await port_open(VITE_PORT):
            await agent.start_fallback()

        if open_browser:
            await asyncio.sleep(0.05)
            webbrowser.open(TARGET_URL)

        await asyncio.Event().wait()


if __name__ == "__main__":
    background_only = "--background" in sys.argv

    # Se o agente já está rodando, a segunda execução só abre o endereço.
    if port_is_open_sync(WS_PORT):
        if not background_only:
            webbrowser.open(TARGET_URL)
        raise SystemExit(0)

    try:
        asyncio.run(run_agent(open_browser=not background_only))
    except KeyboardInterrupt:
        pass
