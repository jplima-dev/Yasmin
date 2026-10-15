"""Adapta capacidades já existentes sem passar dependências legadas ao núcleo."""

import csv
import io
import subprocess
import time
from pathlib import Path

import apps_yas
import comandos_yasm

from .ferramentas import Ferramenta, RegistroFerramentas
from .modelos import ResultadoFerramenta, ResultadoVerificacao, Risco, StatusVerificacao
from .verificacao import Verificador


def processos_ativos() -> set[str] | None:
    try:
        saida = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                               text=True, timeout=5, check=True)
        return {linha[0].lower() for linha in csv.reader(io.StringIO(saida.stdout)) if linha}
    except (OSError, subprocess.SubprocessError):
        try:
            saida = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "Get-Process | Select-Object -ExpandProperty ProcessName"],
                capture_output=True, text=True, timeout=5, check=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return {f"{nome.strip().lower()}.exe" for nome in saida.stdout.splitlines()
                    if nome.strip()}
        except (OSError, subprocess.SubprocessError):
            return None


def localizar_aplicativo(nome: str) -> ResultadoFerramenta:
    dados = apps_yas.APLICATIVOS.get(nome)
    if not dados:
        return ResultadoFerramenta(False, erro=f"Aplicativo não catalogado: {nome}")
    candidatos = tuple(dados["candidatos"])
    caminho = apps_yas._encontrar_executavel(candidatos)
    if caminho and (caminho not in candidatos or Path(caminho).exists() or caminho.startswith("ms-")):
        return ResultadoFerramenta(True, {"nome": nome, "caminho": caminho})
    instalado = apps_yas._encontrar_app_instalado(nome)
    if instalado:
        return ResultadoFerramenta(True, {"nome": nome, "caminho": instalado["caminho"]})
    return ResultadoFerramenta(False, erro=f"Executável de {nome} não encontrado")


def abrir_aplicativo(nome: str) -> ResultadoFerramenta:
    mensagem = apps_yas.abrir_aplicativo(nome)
    if not mensagem or not mensagem.lower().startswith("abrindo "):
        return ResultadoFerramenta(False, erro=mensagem or "Aplicativo não abriu")
    return ResultadoFerramenta(True, {"nome": nome, "mensagem": mensagem})


def fechar_aplicativo(nome: str) -> ResultadoFerramenta:
    mensagem = apps_yas.fechar_aplicativo(nome)
    if not mensagem or not mensagem.lower().startswith("fechando "):
        return ResultadoFerramenta(False, erro=mensagem or "Aplicativo não foi fechado")
    return ResultadoFerramenta(True, {"nome": nome, "mensagem": mensagem})


def pesquisar_web(consulta: str) -> ResultadoFerramenta:
    resultados = comandos_yasm.buscar_web(consulta)
    return ResultadoFerramenta(bool(resultados), {"resultados": resultados} if resultados else None,
                               None if resultados else "Nenhum resultado obtido")


def verificar_executavel(etapa, observacao) -> ResultadoVerificacao:
    dados = observacao.dados.get("resultado") or {}
    if observacao.dados.get("sucesso") and dados.get("caminho"):
        return ResultadoVerificacao(StatusVerificacao.SUCESSO, 0.95, (f"Executável localizado: {dados['caminho']}",))
    return ResultadoVerificacao(StatusVerificacao.FALHA, 0.95, (observacao.dados.get("erro") or "Não localizado",))


def verificar_processo(etapa, observacao) -> ResultadoVerificacao:
    if not observacao.dados.get("sucesso"):
        return ResultadoVerificacao(StatusVerificacao.FALHA, 1.0, (observacao.dados.get("erro") or "Abertura falhou",))
    esperados = {nome.lower() for nome in apps_yas.PROCESSOS.get(etapa.parametros["nome"], ())}
    if not esperados:
        return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.2, ("Sem processo conhecido para verificar",))
    for tentativa in range(3):
        ativos = processos_ativos()
        if ativos is None:
            return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.2, ("Não foi possível consultar processos",))
        encontrados = esperados & ativos
        if encontrados:
            return ResultadoVerificacao(StatusVerificacao.SUCESSO, 0.98,
                                        (f"Processo ativo: {sorted(encontrados)[0]}",))
        if tentativa < 2:
            time.sleep(0.5)
    return ResultadoVerificacao(StatusVerificacao.FALHA, 0.9, ("Processo esperado ausente",))


def verificar_processo_encerrado(etapa, observacao) -> ResultadoVerificacao:
    if not observacao.dados.get("sucesso"):
        return ResultadoVerificacao(StatusVerificacao.FALHA, 1.0,
                                    (observacao.dados.get("erro") or "Fechamento falhou",))
    esperados = {nome.lower() for nome in apps_yas.PROCESSOS.get(etapa.parametros["nome"], ())}
    if not esperados:
        return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.2, ("Sem processo conhecido para verificar",))
    for tentativa in range(3):
        ativos = processos_ativos()
        if ativos is None:
            return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.2, ("Não foi possível consultar processos",))
        if not esperados.intersection(ativos):
            return ResultadoVerificacao(StatusVerificacao.SUCESSO, 0.98, ("Processo encerrado",))
        if tentativa < 2:
            time.sleep(0.3)
    return ResultadoVerificacao(StatusVerificacao.FALHA, 0.9, ("Processo continua ativo",))


def criar_adaptadores() -> tuple[RegistroFerramentas, Verificador]:
    registro = RegistroFerramentas()
    registro.registrar(Ferramenta("localizar_aplicativo", "Localiza executável instalado", ("nome",),
                                 Risco.BAIXO, localizar_aplicativo, "executavel"))
    registro.registrar(Ferramenta("abrir_aplicativo", "Abre um aplicativo", ("nome",),
                                 Risco.MEDIO, abrir_aplicativo, "processo"))
    registro.registrar(Ferramenta("fechar_aplicativo", "Encerra à força um aplicativo e sua árvore de processos",
                                 ("nome",), Risco.ALTO, fechar_aplicativo, "processo_encerrado"))
    registro.registrar(Ferramenta("pesquisar_web", "Pesquisa informações atuais na internet", ("consulta",),
                                 Risco.BAIXO, pesquisar_web, "resultados_web"))
    verificador = Verificador()
    verificador.registrar("executavel", verificar_executavel)
    verificador.registrar("processo", verificar_processo)
    verificador.registrar("processo_encerrado", verificar_processo_encerrado)
    verificador.registrar("resultados_web", lambda etapa, obs: ResultadoVerificacao(
        StatusVerificacao.SUCESSO if obs.dados.get("resultado", {}).get("resultados") else StatusVerificacao.FALHA,
        0.9, ("Resultados de busca presentes",) if obs.dados.get("resultado", {}).get("resultados")
        else ("Busca sem resultados",)))
    return registro, verificador
