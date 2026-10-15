"""Disponibilidade assíncrona do repositório MySQL, sem armazenamento alternativo."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from agente.modelos import Objetivo

from .mysql_memoria import RepositorioMemoriaMySQL

log = logging.getLogger("yasm.agente")


class MemoriaMySQLDisponivel:
    def __init__(self, repositorio: RepositorioMemoriaMySQL, pasta_legada: Path,
                 intervalo_tentativa: float = 10.0):
        self.repositorio = repositorio
        self.pasta_legada = Path(pasta_legada)
        self.intervalo_tentativa = intervalo_tentativa
        self._pronta = threading.Event()
        self._fechar = threading.Event()
        self._trava = threading.Lock()
        self._thread: threading.Thread | None = None
        self._iniciar_preparo()

    @property
    def disponivel(self) -> bool:
        return self._pronta.is_set()

    def _iniciar_preparo(self) -> None:
        with self._trava:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._preparar, daemon=True,
                                            name="yasm-memoria-mysql")
            self._thread.start()

    def _preparar(self) -> None:
        while not self._fechar.is_set():
            try:
                self.repositorio.preparar()
                self.repositorio.migrar_memorias_existentes(self.pasta_legada)
                self._pronta.set()
                log.debug("[AGENTE] Memória MySQL pronta")
                while self._pronta.is_set() and not self._fechar.wait(0.2):
                    pass
            except Exception as erro:
                log.debug("[AGENTE] Memória MySQL indisponível; nova tentativa: %s", erro)
                self._fechar.wait(self.intervalo_tentativa)

    def _usar(self, metodo: str, *args, padrao=None):
        if not self.disponivel:
            return padrao
        try:
            return getattr(self.repositorio, metodo)(*args)
        except Exception as erro:
            log.debug("[AGENTE] Memória MySQL deixou de responder: %s", erro)
            self._pronta.clear()
            return padrao

    def recuperar(self, objetivo: Objetivo, limite: int = 8) -> list[dict]:
        return self._usar("recuperar", objetivo, limite, padrao=[])

    def recuperar_preferencias(self, limite: int = 12) -> list[dict]:
        return self._usar("recuperar_preferencias", limite, padrao=[])

    def guardar(self, categoria: str, chave: str, valor, origem: str,
                importancia: float = 0.8, confianca: float = 0.95) -> bool:
        if not self.disponivel:
            return False
        try:
            self.repositorio.salvar(categoria, chave, valor, origem, importancia, confianca)
            return True
        except Exception as erro:
            log.debug("[AGENTE] Falha ao guardar memória: %s", erro)
            self._pronta.clear()
            return False

    def esquecer(self, categoria: str, chave: str, origem: str = "conversa") -> bool:
        return bool(self._usar("esquecer", categoria, chave, origem, padrao=False))

    def registrar_experiencia(self, objetivo: Objetivo, aplicativo: str) -> None:
        self._usar("registrar_experiencia", objetivo, aplicativo)

    def registrar_objetivo(self, objetivo: Objetivo, status: str) -> None:
        self._usar("registrar_objetivo", objetivo, status)

    def fechar(self) -> None:
        self._fechar.set()
