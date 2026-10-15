from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ECOSYSTEM_ROOT = PROJECT_ROOT.parent


def test_inkdriver_loads_workspace_module_shell():
    html = (PROJECT_ROOT / "web/index.html").read_text(encoding="utf-8")
    assert 'data-module-id="drive2"' in html
    assert 'href="/static/css/workspace.css"' in html
    assert 'src="http://127.0.0.1:8790/core/module-bootstrap.js"' in html


def test_workspace_style_uses_shared_theme_tokens():
    css = (PROJECT_ROOT / "web/css/workspace.css").read_text(encoding="utf-8")
    assert ":root[data-theme]" in css
    assert "var(--surface-gradient" in css
    assert "var(--accent-gradient" in css


def test_dropzone_can_send_files_to_inkdriver():
    source = (ECOSYSTEM_ROOT / "workspace-os/web/core/dropzone.js").read_text(encoding="utf-8")
    assert 'moduleAction("drive2", "Salvar no InkDriver", { inputId: "uploadInput" })' in source
