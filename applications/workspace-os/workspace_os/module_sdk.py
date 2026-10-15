from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from . import __version__
from .registry import MODULE_ID


SUPPORTED_KINDS = {"static-web", "web-service", "remote-web", "desktop", "planned"}
GENERATOR_TYPES = {"static-web", "node-service", "python-service"}
REQUIRED_FIELDS = ("schemaVersion", "id", "name", "category", "kind")
SAFE_SLUG = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


@dataclass(frozen=True)
class ValidationIssue:
    level: str
    code: str
    message: str


@dataclass(frozen=True)
class ModuleValidation:
    module_id: str
    folder: str
    manifest: str
    issues: tuple[ValidationIssue, ...]

    @property
    def level(self) -> str:
        if any(issue.level == "error" for issue in self.issues):
            return "error"
        if any(issue.level == "warning" for issue in self.issues):
            return "warning"
        return "ok"


@dataclass(frozen=True)
class ModuleValidationReport:
    modules: tuple[ModuleValidation, ...]
    global_issues: tuple[ValidationIssue, ...] = ()

    @property
    def errors(self) -> int:
        return sum(issue.level == "error" for issue in self.global_issues) + sum(
            issue.level == "error" for module in self.modules for issue in module.issues
        )

    @property
    def warnings(self) -> int:
        return sum(issue.level == "warning" for issue in self.global_issues) + sum(
            issue.level == "warning" for module in self.modules for issue in module.issues
        )

    @property
    def exit_code(self) -> int:
        return 1 if self.errors else 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.exit_code == 0,
            "summary": {"modules": len(self.modules), "warnings": self.warnings, "errors": self.errors},
            "globalIssues": [asdict(issue) for issue in self.global_issues],
            "modules": [
                {
                    "id": module.module_id,
                    "folder": module.folder,
                    "manifest": module.manifest,
                    "level": module.level,
                    "issues": [asdict(issue) for issue in module.issues],
                }
                for module in self.modules
            ],
        }

    def render(self, *, ascii_only: bool = False) -> str:
        symbols = {
            "ok": "[OK]" if ascii_only else "✓",
            "warning": "[AVISO]" if ascii_only else "⚠",
            "error": "[ERRO]" if ascii_only else "✗",
        }
        lines = ["Workspace Module Validator", ""]
        for issue in self.global_issues:
            lines.append(f"{symbols[issue.level]} workspace")
            lines.append(f"  {issue.message}")
        for module in self.modules:
            lines.append(f"{symbols[module.level]} {module.module_id}")
            for issue in module.issues:
                lines.append(f"  {issue.message}")
        lines.extend([
            "",
            f"{len(self.modules)} módulo(s), {self.warnings} aviso(s), {self.errors} erro(s)",
        ])
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    module_id: str
    description: str
    module_type: str
    category: str = "utilities"
    icon: str = "app"
    port: int | None = None
    add_to_order: bool = True
    managed_service: bool = True
    auto_start: bool = False
    include_preferences: bool = False
    include_backup: bool = False


@dataclass(frozen=True)
class ScaffoldResult:
    module_path: Path
    manifest_path: Path
    config_updated: bool
    files: tuple[str, ...]


def _add_issue(issues: list[ValidationIssue], level: str, code: str, message: str) -> None:
    candidate = ValidationIssue(level, code, message)
    if candidate not in issues:
        issues.append(candidate)


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _valid_http_url(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and (port is None or 1 <= port <= 65535)


def _safe_entry(folder: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = (folder / value).resolve()
    try:
        candidate.relative_to(folder.resolve())
    except ValueError:
        return None
    return candidate


def _load_registry_config(config_path: Path) -> tuple[dict[str, Any] | None, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _add_issue(issues, "error", "REGISTRY_INVALID", f"config/modules.json inválido: {exc}")
        return None, issues
    if not isinstance(payload, dict):
        _add_issue(issues, "error", "REGISTRY_TYPE", "config/modules.json precisa conter um objeto JSON.")
        return None, issues
    for field in ("trustedCommandModules", "moduleOrder", "modules"):
        if not isinstance(payload.get(field, []), list):
            _add_issue(issues, "error", "REGISTRY_FIELD", f'campo "{field}" do registro precisa ser uma lista.')
    return payload, issues


def validate_modules(ecosystem_root: Path, config_path: Path) -> ModuleValidationReport:
    ecosystem_root = ecosystem_root.resolve()
    config_path = config_path.resolve()
    config, global_issues = _load_registry_config(config_path)
    trusted = set(config.get("trustedCommandModules", [])) if config else set()
    reports: list[ModuleValidation] = []
    parsed: list[tuple[Path, dict[str, Any], list[ValidationIssue]]] = []

    for manifest_path in sorted(ecosystem_root.glob("*/ink-module.json")):
        folder = manifest_path.parent
        issues: list[ValidationIssue] = []
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            _add_issue(issues, "error", "MANIFEST_JSON", f"manifesto JSON inválido: {exc}")
            reports.append(ModuleValidation(folder.name, folder.name, str(manifest_path), tuple(issues)))
            continue
        if not isinstance(raw, dict):
            _add_issue(issues, "error", "MANIFEST_TYPE", "o manifesto precisa conter um objeto JSON.")
            reports.append(ModuleValidation(folder.name, folder.name, str(manifest_path), tuple(issues)))
            continue
        module_id = raw.get("id") if isinstance(raw.get("id"), str) else folder.name
        for field in REQUIRED_FIELDS:
            if field not in raw or raw[field] in (None, ""):
                _add_issue(issues, "error", "REQUIRED_FIELD", f'campo obrigatório "{field}" ausente.')
        if raw.get("schemaVersion") != 2:
            _add_issue(issues, "error", "SCHEMA_VERSION", "schemaVersion precisa ser 2.")
        if not isinstance(raw.get("id"), str) or not MODULE_ID.fullmatch(str(raw.get("id", ""))):
            _add_issue(issues, "error", "INVALID_ID", f'ID inválido: {raw.get("id")!r}.')
        for field in ("name", "category"):
            if not isinstance(raw.get(field), str) or not raw.get(field, "").strip():
                _add_issue(issues, "error", "INVALID_TEXT", f'campo "{field}" precisa ser texto não vazio.')
        if not isinstance(raw.get("description"), str) or not raw.get("description", "").strip():
            _add_issue(issues, "warning", "DESCRIPTION_MISSING", 'campo "description" ausente ou vazio.')
        kind = raw.get("kind")
        if kind not in SUPPORTED_KINDS:
            _add_issue(issues, "error", "INVALID_KIND", f"kind não suportado: {kind!r}.")
        if not isinstance(raw.get("icon"), str) or not raw.get("icon", "").strip():
            _add_issue(issues, "warning", "ICON_MISSING", 'campo "icon" ausente ou vazio; o Core usará "app".')
        version = raw.get("version")
        if not isinstance(version, str) or not SEMVER.fullmatch(version):
            _add_issue(issues, "warning", "VERSION_INVALID", 'campo "version" deveria usar SemVer, por exemplo "1.0.0".')
        if not isinstance(raw.get("minCoreVersion"), str) or not raw.get("minCoreVersion", "").strip():
            _add_issue(issues, "warning", "CORE_VERSION_MISSING", 'campo "minCoreVersion" ausente.')

        entry = _safe_entry(folder, raw.get("entryFile"))
        if kind == "static-web" and entry is None:
            _add_issue(issues, "error", "ENTRY_REQUIRED", 'módulo static-web exige "entryFile" seguro.')
        elif raw.get("entryFile") is not None and entry is None:
            _add_issue(issues, "error", "ENTRY_INVALID", "entryFile é vazio ou aponta para fora da pasta do módulo.")
        if entry is not None and not entry.is_file():
            _add_issue(issues, "error", "ENTRY_MISSING", f'entrypoint "{raw.get("entryFile")}" não encontrado.')

        command = raw.get("command", [])
        if not _is_string_list(command) or any(not item.strip() for item in command):
            _add_issue(issues, "error", "COMMAND_INVALID", "command precisa ser uma lista de argumentos não vazios.")
        if command and module_id not in trusted:
            _add_issue(issues, "error", "COMMAND_UNTRUSTED", "o comando existe, mas o ID não está em trustedCommandModules.")
        if "autoStart" in raw and not isinstance(raw["autoStart"], bool):
            _add_issue(issues, "error", "AUTOSTART_TYPE", "autoStart precisa ser booleano.")
        if raw.get("autoStart") and not command:
            _add_issue(issues, "error", "AUTOSTART_COMMAND", "autoStart exige um command.")

        for field in ("url", "serviceUrl", "healthUrl"):
            if field in raw and not _valid_http_url(raw[field]):
                _add_issue(issues, "error", "URL_INVALID", f"{field} precisa ser uma URL HTTP(S) válida.")
        service_endpoint = raw.get("serviceUrl") or raw.get("url")
        if kind in {"web-service", "remote-web"} and not _valid_http_url(service_endpoint):
            _add_issue(issues, "error", "URL_REQUIRED", f'{kind} exige uma URL válida em "url" ou "serviceUrl".')
        if kind == "web-service" and not _valid_http_url(raw.get("healthUrl")):
            _add_issue(issues, "warning", "HEALTH_URL_MISSING", 'web-service deveria declarar "healthUrl".')

        capabilities = raw.get("capabilities", {})
        if not isinstance(capabilities, dict):
            _add_issue(issues, "error", "CAPABILITIES_TYPE", "capabilities precisa ser um objeto.")
        else:
            for field in ("export", "import", "print", "offline"):
                if field in capabilities and not isinstance(capabilities[field], bool):
                    _add_issue(issues, "error", "CAPABILITY_TYPE", f"capabilities.{field} precisa ser booleano.")
            for field in ("shortcuts", "permissions"):
                if field in capabilities and not _is_string_list(capabilities[field]):
                    _add_issue(issues, "error", "CAPABILITY_LIST", f"capabilities.{field} precisa ser uma lista de textos.")
        for field in ("instructions", "keywords", "permissions"):
            if field in raw and not _is_string_list(raw[field]):
                _add_issue(issues, "error", "LIST_TYPE", f'{field} precisa ser uma lista de textos.')
        data_version = raw.get("dataSchemaVersion", 1)
        if isinstance(data_version, bool) or not isinstance(data_version, int) or data_version < 1:
            _add_issue(issues, "error", "DATA_SCHEMA_VERSION", "dataSchemaVersion precisa ser um inteiro positivo.")
        migrations = raw.get("migrations", [])
        if not isinstance(migrations, list) or not all(isinstance(item, dict) for item in migrations):
            _add_issue(issues, "error", "MIGRATIONS_TYPE", "migrations precisa ser uma lista de objetos.")
        parsed.append((manifest_path, raw, issues))

    by_id: dict[str, list[tuple[Path, list[ValidationIssue]]]] = {}
    for manifest_path, raw, issues in parsed:
        module_id = str(raw.get("id", manifest_path.parent.name))
        by_id.setdefault(module_id, []).append((manifest_path, issues))
    for module_id, entries in by_id.items():
        if len(entries) > 1:
            folders = ", ".join(entry[0].parent.name for entry in entries)
            for _, issues in entries:
                _add_issue(issues, "error", "DUPLICATE_ID", f'ID duplicado "{module_id}" nas pastas: {folders}.')
    endpoints: dict[tuple[str, int], list[tuple[str, list[ValidationIssue]]]] = {}
    for manifest_path, raw, issues in parsed:
        if raw.get("kind") != "web-service":
            continue
        url = raw.get("healthUrl") or raw.get("serviceUrl") or raw.get("url")
        if not _valid_http_url(url):
            continue
        parsed_url = urlparse(url)
        port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
        endpoints.setdefault((str(parsed_url.hostname).casefold(), port), []).append((
            str(raw.get("id", manifest_path.parent.name)), issues,
        ))
    for (host, port), entries in endpoints.items():
        if len(entries) > 1:
            module_ids = ", ".join(item[0] for item in entries)
            for _, issues in entries:
                _add_issue(issues, "error", "SERVICE_PORT_CONFLICT", f"serviços compartilham {host}:{port}: {module_ids}.")
    for manifest_path, raw, issues in parsed:
        reports.append(ModuleValidation(
            str(raw.get("id", manifest_path.parent.name)), manifest_path.parent.name,
            str(manifest_path), tuple(issues),
        ))

    known_ids = {module.module_id for module in reports if MODULE_ID.fullmatch(module.module_id)}
    if config:
        for field in ("trustedCommandModules", "moduleOrder"):
            for item in config.get(field, []):
                if not isinstance(item, str) or not MODULE_ID.fullmatch(item):
                    _add_issue(global_issues, "error", "REGISTRY_ID", f'{field} contém ID inválido: {item!r}.')
                elif item not in known_ids:
                    _add_issue(global_issues, "warning", "REGISTRY_STALE_ID", f'{field} referencia módulo ausente: "{item}".')
    reports.sort(key=lambda item: item.module_id.casefold())
    return ModuleValidationReport(tuple(reports), tuple(global_issues))


def _validate_spec(spec: ModuleSpec) -> None:
    for label, value in (("nome", spec.name), ("descrição", spec.description), ("categoria", spec.category), ("ícone", spec.icon)):
        if not isinstance(value, str) or not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError(f"{label} precisa ser texto não vazio e sem caracteres de controle.")
    if not SAFE_SLUG.fullmatch(spec.module_id):
        raise ValueError("ID inválido. Use 2–40 caracteres: letra minúscula inicial, números e hífens.")
    if spec.module_type not in GENERATOR_TYPES:
        raise ValueError(f"Tipo não suportado pelo gerador: {spec.module_type}.")
    if not SAFE_SLUG.fullmatch(spec.category):
        raise ValueError("Categoria inválida. Use o mesmo formato seguro de um ID.")
    if spec.module_type != "static-web" and (not isinstance(spec.port, int) or not 1 <= spec.port <= 65535):
        raise ValueError("Serviços exigem uma porta entre 1 e 65535.")
    if spec.auto_start and not spec.managed_service:
        raise ValueError("autoStart só pode ser usado em um serviço gerenciado pelo Workspace.")


def _core_origin(config: dict[str, Any]) -> str:
    origin = config.get("origin", {}) if isinstance(config, dict) else {}
    scheme = origin.get("scheme", "http")
    host = origin.get("host", "127.0.0.1")
    port = origin.get("port", 8790)
    return f"{scheme}://{host}:{port}"


def _manifest_for(spec: ModuleSpec, core_origin: str) -> dict[str, Any]:
    permissions = ["storage:local"] if spec.include_preferences or spec.include_backup else []
    kind = "static-web" if spec.module_type == "static-web" else "web-service"
    manifest: dict[str, Any] = {
        "schemaVersion": 2,
        "id": spec.module_id,
        "name": spec.name.strip(),
        "category": spec.category,
        "description": spec.description.strip(),
        "kind": kind,
        "entryFile": "index.html",
        "icon": spec.icon.strip(),
        "version": "0.1.0",
        "minCoreVersion": __version__,
        "keywords": [],
        "capabilities": {
            "export": spec.include_backup,
            "import": spec.include_backup,
            "print": False,
            "offline": spec.module_type == "static-web",
            "shortcuts": [],
            "permissions": permissions,
        },
        "dataSchemaVersion": 1,
        "migrations": [],
        "instructions": ["Abra o módulo pelo painel do Workspace OS."],
    }
    if kind == "web-service":
        base_url = f"http://127.0.0.1:{spec.port}"
        manifest.update({"url": base_url, "healthUrl": f"{base_url}/api/health"})
        if spec.managed_service:
            manifest["command"] = ["node", "server.js"] if spec.module_type == "node-service" else ["{python}", "server.py"]
            manifest["autoStart"] = spec.auto_start
            manifest["capabilities"]["permissions"].append("process:start")
    return manifest


def _html_template(spec: ModuleSpec, core_origin: str) -> str:
    name = html.escape(spec.name.strip())
    description = html.escape(spec.description.strip())
    module_id = html.escape(spec.module_id)
    return f"""<!doctype html>
<html lang="pt-BR" data-module-id="{module_id}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark light">
  <title>{name}</title>
  <link rel="stylesheet" href="{core_origin}/core/tool-shell.css">
  <link rel="stylesheet" href="./styles.css">
</head>
<body class="ink-tool">
  <main class="tool-shell">
    <header class="tool-header">
      <div class="tool-title"><span class="tool-mark">{html.escape(spec.icon[:2].upper())}</span><div><h1>{name}</h1><p>{description}</p></div></div>
    </header>
    <section class="tool-card">
      <div class="tool-card-body module-example">
        <p id="status">Módulo carregado.</p>
        <button class="tool-button primary" id="action" type="button">Executar ação</button>
        {"<button class=\"tool-button\" id=\"publish-backup\" type=\"button\">Publicar backup</button>" if spec.include_backup else ""}
      </div>
    </section>
  </main>
  <script type="module" src="{core_origin}/core/module-bootstrap.js"></script>
  <script type="module" src="./app.js"></script>
</body>
</html>
"""


def _app_template(spec: ModuleSpec) -> str:
    module_id = json.dumps(spec.module_id, ensure_ascii=False)
    storage_line = f"const store = Mega.storage.namespace({module_id});\nlet state = store.get(\"state\", {{ count: 0 }});" if spec.include_preferences else "let state = { count: 0 };"
    save_line = 'store.set("state", state);' if spec.include_preferences else ""
    backup = ""
    cleanup = ["unsubscribeSettings();"]
    if spec.include_backup:
        backup = f"""
const backup = Mega.backup.register({{
  moduleId: {module_id},
  schemaVersion: 1,
  exportData: async () => ({{ ...state }}),
  importData: async (data) => {{
    state = {{ count: Number(data?.count || 0) }};
    {save_line}
    render();
  }},
}});
document.querySelector("#publish-backup").addEventListener("click", async () => {{
  await backup.publish();
  Mega.ui.toast("Snapshot publicado no backup portátil.", {{ tone: "success" }});
}});
"""
        cleanup.append("backup.unregister();")
    return f"""{storage_line}
const status = document.querySelector("#status");

function render() {{
  status.textContent = `Ação executada ${{state.count}} vez(es).`;
}}

document.querySelector("#action").addEventListener("click", () => {{
  state = {{ ...state, count: state.count + 1 }};
  {save_line}
  render();
  Mega.ui.toast("Ação concluída.");
}});

const unsubscribeSettings = Mega.settings.subscribe((settings) => {{
  document.documentElement.lang = settings.language || "pt-BR";
}});
{backup}
addEventListener("pagehide", () => {{
  {" ".join(cleanup)}
}}, {{ once: true }});

render();
"""


def _styles_template() -> str:
    return """.module-example {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3, 0.75rem);
  align-items: center;
}

.module-example p {
  flex-basis: 100%;
  margin: 0;
}
"""


def _node_server_template(spec: ModuleSpec) -> str:
    return f"""const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const host = process.env.HOST || "127.0.0.1";
const port = Number(process.env.PORT || {spec.port});
const moduleName = {json.dumps(spec.name, ensure_ascii=False)};
const files = new Map([
  ["/", ["index.html", "text/html; charset=utf-8"]],
  ["/index.html", ["index.html", "text/html; charset=utf-8"]],
  ["/app.js", ["app.js", "text/javascript; charset=utf-8"]],
  ["/styles.css", ["styles.css", "text/css; charset=utf-8"]],
]);

const server = http.createServer((request, response) => {{
  const pathname = new URL(request.url, `http://${{request.headers.host || host}}`).pathname;
  if (pathname === "/api/health") {{
    response.writeHead(200, {{ "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" }});
    response.end(JSON.stringify({{ status: "ok", module: {json.dumps(spec.module_id)} }}));
    return;
  }}
  const target = files.get(pathname);
  if (!target) {{ response.writeHead(404); response.end("Not found"); return; }}
  fs.readFile(path.join(__dirname, target[0]), (error, content) => {{
    if (error) {{ response.writeHead(500); response.end("Read error"); return; }}
    response.writeHead(200, {{ "Content-Type": target[1], "X-Content-Type-Options": "nosniff" }});
    response.end(content);
  }});
}});

server.listen(port, host, () => console.log(`${{moduleName}} em http://${{host}}:${{port}}`));
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => server.close(() => process.exit(0)));
"""


def _python_server_template(spec: ModuleSpec) -> str:
    return f'''from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "{spec.port}"))
MODULE_NAME = {spec.name!r}
FILES = {{
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            body = json.dumps({{"status": "ok", "module": {spec.module_id!r}}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
        elif path in FILES:
            filename, content_type = FILES[path]
            body = (ROOT / filename).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("X-Content-Type-Options", "nosniff")
        else:
            body = b"Not found"
            self.send_response(404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{{self.address_string()}} - {{format % args}}")


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"{{MODULE_NAME}} em http://{{HOST}}:{{PORT}}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
'''


def _readme_template(spec: ModuleSpec) -> str:
    run = "Abra pelo Workspace OS."
    if spec.module_type == "node-service":
        run = "Execute `node server.js` ou inicie pelo Workspace OS quando o serviço estiver autorizado."
    elif spec.module_type == "python-service":
        run = "Execute `python server.py` ou inicie pelo Workspace OS quando o serviço estiver autorizado."
    return f"""# {spec.name}

{spec.description}

ID público: `{spec.module_id}`. Não reutilize ou renomeie esse ID depois de publicar dados.

## Executar

{run}

Valide o contrato a partir de `workspace-os/`:

```powershell
npm run validate-modules
```
"""


def _files_for(spec: ModuleSpec, core_origin: str) -> dict[str, str]:
    files = {
        "ink-module.json": json.dumps(_manifest_for(spec, core_origin), ensure_ascii=False, indent=2) + "\n",
        "index.html": _html_template(spec, core_origin),
        "app.js": _app_template(spec),
        "styles.css": _styles_template(),
        "README.md": _readme_template(spec),
    }
    if spec.module_type == "node-service":
        files["server.js"] = _node_server_template(spec)
        files["package.json"] = json.dumps({
            "name": spec.module_id, "version": "0.1.0", "private": True,
            "scripts": {"start": "node server.js"},
        }, indent=2) + "\n"
    elif spec.module_type == "python-service":
        files["server.py"] = _python_server_template(spec)
    return files


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def create_module(spec: ModuleSpec, ecosystem_root: Path, config_path: Path) -> ScaffoldResult:
    _validate_spec(spec)
    ecosystem_root = ecosystem_root.resolve()
    config_path = config_path.resolve()
    config, issues = _load_registry_config(config_path)
    if config is None or any(issue.level == "error" for issue in issues):
        raise ValueError(issues[0].message if issues else "Registro central inválido.")
    target = (ecosystem_root / spec.module_id).resolve()
    try:
        target.relative_to(ecosystem_root)
    except ValueError as exc:
        raise ValueError("O destino do módulo aponta para fora do ecossistema.") from exc
    if target.exists():
        raise FileExistsError(f"O destino já existe: {target}")
    existing = validate_modules(ecosystem_root, config_path)
    if any(module.module_id == spec.module_id for module in existing.modules):
        raise FileExistsError(f'O ID "{spec.module_id}" já está registrado.')
    if spec.port is not None:
        origin = config.get("origin", {})
        if isinstance(origin, dict) and origin.get("port") == spec.port:
            raise ValueError(f"A porta {spec.port} já pertence ao Core do Workspace.")
        for manifest_path in ecosystem_root.glob("*/ink-module.json"):
            try:
                raw = json.loads(manifest_path.read_text(encoding="utf-8"))
                url = raw.get("healthUrl") or raw.get("url") if isinstance(raw, dict) else None
                parsed = urlparse(url) if isinstance(url, str) else None
                used_port = parsed.port if parsed else None
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                continue
            if used_port == spec.port:
                raise ValueError(f"A porta {spec.port} já é usada pelo módulo {raw.get('id', manifest_path.parent.name)}.")

    original_config = config_path.read_bytes()
    config_updated = False
    staging = Path(tempfile.mkdtemp(prefix=f".{spec.module_id}-", dir=ecosystem_root))
    files = _files_for(spec, _core_origin(config))
    try:
        for relative, content in files.items():
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="\n")
        updated = json.loads(json.dumps(config))
        if spec.add_to_order and spec.module_id not in updated.setdefault("moduleOrder", []):
            updated["moduleOrder"].append(spec.module_id)
            config_updated = True
        if spec.module_type != "static-web" and spec.managed_service:
            trusted = updated.setdefault("trustedCommandModules", [])
            if spec.module_id not in trusted:
                trusted.append(spec.module_id)
                config_updated = True
        if config_updated:
            _write_json_atomic(config_path, updated)
        staging.replace(target)
    except Exception:
        if config_updated:
            config_path.write_bytes(original_config)
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return ScaffoldResult(target, target / "ink-module.json", config_updated, tuple(sorted(files)))


def _prompt(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}:\n> ").strip()
    return value or (default or "")


def _confirm(label: str, default: bool = True) -> bool:
    hint = "S/n" if default else "s/N"
    while True:
        value = input(f"{label} [{hint}]:\n> ").strip().casefold()
        if not value:
            return default
        if value in {"s", "sim", "y", "yes"}:
            return True
        if value in {"n", "não", "nao", "no"}:
            return False
        print("Responda sim ou não.")


def _slugify(value: str) -> str:
    import unicodedata
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", normalized))[:40]


def interactive_create(ecosystem_root: Path, config_path: Path) -> ScaffoldResult:
    print("Workspace Module Generator\n")
    name = _prompt("Nome do módulo")
    module_id = _prompt("ID", _slugify(name))
    description = _prompt("Descrição")
    print("Tipo:\n1. Web estático\n2. Serviço Node.js\n3. Serviço Python")
    choice = _prompt("Escolha", "1")
    module_type = {"1": "static-web", "2": "node-service", "3": "python-service"}.get(choice)
    if module_type is None:
        raise ValueError("Tipo inválido. Escolha 1, 2 ou 3.")
    category = _prompt("Categoria", "utilities")
    icon = _prompt("Ícone", "app")
    add_to_order = _confirm("Adicionar ao fim da ordem do launcher?", True)
    include_preferences = _confirm("Incluir exemplo de preferências/armazenamento local?", False)
    include_backup = _confirm("Incluir snapshot no backup portátil?", False)
    port: int | None = None
    managed = False
    auto_start = False
    if module_type != "static-web":
        port = int(_prompt("Porta local", "8800"))
        managed = _confirm("Autorizar o Workspace a iniciar e encerrar este serviço?", True)
        if managed:
            auto_start = _confirm("Iniciar automaticamente com o Workspace?", False)
    spec = ModuleSpec(
        name=name, module_id=module_id, description=description, module_type=module_type,
        category=category, icon=icon, port=port, add_to_order=add_to_order,
        managed_service=managed, auto_start=auto_start,
        include_preferences=include_preferences, include_backup=include_backup,
    )
    return create_module(spec, ecosystem_root, config_path)


def _default_paths() -> tuple[Path, Path]:
    workspace_root = Path(__file__).resolve().parents[1]
    return workspace_root.parent, workspace_root / "config" / "modules.json"


def main(argv: Iterable[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
    parser = argparse.ArgumentParser(description="SDK interno de módulos do Workspace OS")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create", help="cria um módulo de forma interativa")
    create_parser.add_argument("--root", type=Path)
    create_parser.add_argument("--config", type=Path)
    validate_parser = subparsers.add_parser("validate", help="valida os manifestos do ecossistema")
    validate_parser.add_argument("--root", type=Path)
    validate_parser.add_argument("--config", type=Path)
    validate_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    default_root, default_config = _default_paths()
    root = (args.root or default_root).resolve()
    config = (args.config or default_config).resolve()
    try:
        if args.command == "create":
            result = interactive_create(root, config)
            print(f"\nMódulo criado em: {result.module_path}")
            print("Próximos passos: implemente a funcionalidade e rode `npm run validate-modules`.")
            return 0
        report = validate_modules(root, config)
        if args.json:
            print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        else:
            try:
                print(report.render(), end="")
            except UnicodeEncodeError:
                print(report.render(ascii_only=True), end="")
        return report.exit_code
    except (EOFError, KeyboardInterrupt):
        print("\nOperação cancelada.")
        return 130
    except (OSError, ValueError) as exc:
        print(f"Erro: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
