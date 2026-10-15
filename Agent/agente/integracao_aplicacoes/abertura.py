"""Adapter de interface gráfica usando o launcher e o registro do Workspace OS."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import webbrowser
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from agente.modelos import (Etapa, Observacao, ResultadoFerramenta,
                           ResultadoVerificacao, StatusVerificacao)

from .descoberta import DescobertaAplicacoes
from .estado import _saude_local


class _SemRedirecionar(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


_abridor = build_opener(_SemRedirecionar)
_ABERTURA_NO_WORKSPACE = ContextVar("abertura_no_workspace", default=False)


@contextmanager
def abertura_no_workspace():
    marcador = _ABERTURA_NO_WORKSPACE.set(True)
    try:
        yield
    finally:
        _ABERTURA_NO_WORKSPACE.reset(marcador)


def _origem(raiz: Path) -> str:
    config = json.loads((raiz / "workspace-os" / "config" / "modules.json").read_text(encoding="utf-8"))
    origin = config["origin"]
    if origin.get("scheme") != "http" or origin.get("host") not in {"127.0.0.1", "localhost"}:
        raise ValueError("Origem local do Workspace OS inválida")
    porta = int(origin["port"])
    if not 1 <= porta <= 65535:
        raise ValueError("Porta do Workspace OS inválida")
    return f"http://{origin['host']}:{porta}"


def _url_local(url: str) -> bool:
    parsed = urlparse(url)
    try:
        return parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost", "::1"} and parsed.port != 0
    except ValueError:
        return False


def _json(url: str, *, token: str | None = None) -> dict:
    if not _url_local(url):
        raise ValueError("A integração só aceita o servidor local do Workspace OS")
    headers = {"X-Workspace-Token": token, "Content-Type": "application/json"} if token else {}
    request = Request(url, data=b"{}" if token else None, headers=headers,
                      method="POST" if token else "GET")
    try:
        with _abridor.open(request, timeout=0.8) as response:
            return json.load(response)
    except HTTPError as erro:
        try:
            detalhe = json.loads(erro.read(1024)).get("error", erro.reason)
        except (ValueError, AttributeError):
            detalhe = erro.reason
        raise RuntimeError(f"Workspace OS HTTP {erro.code}: {detalhe}") from erro


def _pagina_ativa(url: str) -> bool:
    if not _url_local(url):
        return False
    try:
        with _abridor.open(url, timeout=0.7) as response:
            return response.status == 200 and "text/html" in response.headers.get("Content-Type", "")
    except (OSError, HTTPError, URLError, ValueError):
        return False


def _aguardar(url: str, limite: float = 2.0) -> bool:
    final = time.monotonic() + limite
    while time.monotonic() < final:
        if _pagina_ativa(url):
            return True
        time.sleep(0.1)
    return _pagina_ativa(url)


def _abrir_navegador(url: str) -> bool:
    if os.name == "nt":
        os.startfile(url)
        return True
    return bool(webbrowser.open(url, new=2))


def abrir_aplicacao(aplicacao: str, descoberta: DescobertaAplicacoes, raiz: Path) -> ResultadoFerramenta:
    por_id = {item.id: item for item in descoberta.aplicacoes}
    contrato = por_id.get(aplicacao)
    if contrato is None:
        return ResultadoFerramenta(False, erro=f"Aplicação desconhecida: {aplicacao}")
    if not contrato.pasta.is_dir() or (contrato.entrada and not contrato.entrada.is_file()):
        return ResultadoFerramenta(False, erro=f"Interface de {contrato.nome} não instalada")
    try:
        origem = _origem(raiz)
        if not _pagina_ativa(origem + "/"):
            launcher = raiz / "workspace-os" / "launcher.py"
            if not launcher.is_file():
                return ResultadoFerramenta(False, erro="Launcher do Workspace OS ausente")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen([sys.executable, str(launcher), "--no-browser"],
                             cwd=launcher.parent, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=flags)
            if not _aguardar(origem + "/"):
                return ResultadoFerramenta(False, erro="Workspace OS não iniciou")
        saude = _json(origem + "/api/health")
        if saude.get("status") != "ok" or saude.get("origin") != origem:
            return ResultadoFerramenta(False, erro="O serviço local não corresponde ao Workspace OS configurado")
        url = origem + "/"
        if aplicacao != "workspace-os":
            modulos = _json(origem + "/api/modules").get("modules", [])
            modulo = next((m for m in modulos if m.get("id") == aplicacao), None)
            if not modulo or not modulo.get("installed") or modulo.get("enabled") is False or modulo.get("compatible") is False:
                return ResultadoFerramenta(False, erro=f"{contrato.nome} indisponível no Workspace OS")
            if not modulo.get("url"):
                return ResultadoFerramenta(False, erro=f"{contrato.nome} não possui interface configurada")
            url = urljoin(origem + "/", str(modulo["url"]))
            if not _url_local(url):
                return ResultadoFerramenta(False, erro="A aplicação requer um endereço local válido")
            precisa_servico = contrato.tipo == "web-service" and bool(contrato.health_url)
            servico_ativo = _saude_local(contrato.health_url) if precisa_servico else None
            if (servico_ativo is False or (not precisa_servico and not _pagina_ativa(url))) and modulo.get("canStart"):
                token = _json(origem + "/api/session").get("token")
                if not isinstance(token, str) or not token:
                    return ResultadoFerramenta(False, erro="Sessão do Workspace OS indisponível")
                iniciado = _json(origem + "/api/modules/" + quote(aplicacao, safe="") + "/start", token=token)
                if not iniciado.get("ok"):
                    return ResultadoFerramenta(False, erro=str(iniciado.get("message") or "Aplicação não iniciou"))
                if precisa_servico:
                    final = time.monotonic() + 3.0
                    while time.monotonic() < final and not _saude_local(contrato.health_url, timeout=0.3):
                        time.sleep(0.1)
                else:
                    _aguardar(url)
            if precisa_servico and not _saude_local(contrato.health_url):
                return ResultadoFerramenta(False, erro=f"Serviço de {contrato.nome} não responde")
            if not _pagina_ativa(url):
                return ResultadoFerramenta(False, erro=f"Interface de {contrato.nome} não responde")
        embutida = _ABERTURA_NO_WORKSPACE.get()
        aceito = embutida or _abrir_navegador(url)
        if not aceito:
            return ResultadoFerramenta(False, erro="O sistema não aceitou abrir o navegador")
        return ResultadoFerramenta(True, {
            "operacao": "abrir_aplicacao_ink", "aplicacao": aplicacao, "nome": contrato.nome,
            "fornecedor": contrato.fornecedor, "url": url, "browser_aceitou": aceito,
            "janela_workspace": embutida,
            "servico_ativo": True if contrato.tipo == "web-service" else None,
            "health_url": contrato.health_url,
            "mensagem": f"Abri {contrato.nome}.",
        })
    except (OSError, HTTPError, URLError, ValueError, KeyError, TypeError, RuntimeError) as erro:
        return ResultadoFerramenta(False, erro=f"Não consegui abrir {contrato.nome}: {erro}")


def verificar_abertura(etapa: Etapa, observacao: Observacao) -> ResultadoVerificacao:
    dados = observacao.dados.get("resultado") or {}
    if not observacao.dados.get("sucesso"):
        return ResultadoVerificacao(StatusVerificacao.FALHA, 1.0,
                                    (str(observacao.dados.get("erro") or "Abertura falhou"),))
    if dados.get("aplicacao") != etapa.parametros.get("aplicacao") or not dados.get("browser_aceitou"):
        return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.2, ("Pedido de abertura não confirmado",))
    url = dados.get("url")
    if not isinstance(url, str) or not _pagina_ativa(url):
        return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.4, ("A interface não responde após a abertura",))
    health_url = dados.get("health_url")
    if health_url and _saude_local(health_url) is not True:
        return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.4,
                                    ("A interface abriu, mas o serviço da aplicação não respondeu",))
    evidencia = "Interface entregue à janela Workspace" if dados.get("janela_workspace") else "Navegador aceitou a abertura"
    return ResultadoVerificacao(StatusVerificacao.SUCESSO, 0.85,
                                (f"Interface HTTP acessível: {url}", evidencia))
