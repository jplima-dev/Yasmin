from __future__ import annotations

import hashlib
import re
import secrets
import threading
import time
from dataclasses import dataclass


SESSION_TTL_SECONDS = 12 * 60 * 60
CONFIRMATION_TTL_SECONDS = 90


class SessionAuth:
    """Ephemeral authentication for privileged local APIs."""

    def __init__(self, ttl_seconds: int = SESSION_TTL_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds
        self._token = secrets.token_urlsafe(32)
        self._created = time.time()
        self._lock = threading.Lock()

    def _refresh_locked(self) -> None:
        if time.time() - self._created >= self.ttl_seconds:
            self._token = secrets.token_urlsafe(32)
            self._created = time.time()

    @property
    def token(self) -> str:
        with self._lock:
            self._refresh_locked()
            return self._token

    @property
    def expires_at(self) -> int:
        with self._lock:
            self._refresh_locked()
            return int(self._created + self.ttl_seconds)

    def verify(self, value: str | None) -> bool:
        return bool(value) and secrets.compare_digest(str(value), self.token)


@dataclass(frozen=True)
class CommandDecision:
    permission: str
    risk: str
    requires_confirmation: bool
    reason: str


class TerminalPolicy:
    """Run unrestricted by default, with the former guarded policy available opt-in."""

    _DANGEROUS = (
        (re.compile(r"\b(remove-item|del|erase|rmdir|rd|rm)\b.*(?:-recurse|-force|/s|/q)", re.I), "Exclusão recursiva ou forçada."),
        (re.compile(r"\b(remove-item|remove-itemproperty|clear-content|del|erase|rmdir|rd|ri|rm)\b", re.I), "Exclusão de arquivo, pasta ou conteúdo."),
        (re.compile(r"\b(format|diskpart|bcdedit|cipher\s+/w)\b", re.I), "Operação que pode alterar disco ou inicialização."),
        (re.compile(r"\bgit\s+(reset\s+--hard|clean\s+-[a-z]*f|restore\b|checkout\s+--|branch\s+-[dD]|stash\s+(drop|clear)|push\b.*--force)", re.I), "Operação Git que pode descartar trabalho local ou sobrescrever histórico remoto."),
        (re.compile(r"\b(stop-process|taskkill|shutdown|restart-computer|stop-computer)\b", re.I), "Operação que encerra processos ou o sistema."),
        (re.compile(r"\b(invoke-expression|iex)\b|\b(downloadstring|downloadfile)\b", re.I), "Execução de conteúdo dinâmico ou remoto."),
        (re.compile(r"\b(set-acl|takeown|icacls|reg\s+(add|delete))\b", re.I), "Alteração de permissões ou configuração do sistema."),
    )
    _WRITE = re.compile(
        r"\b(set-content|add-content|out-file|set-item|new-item|copy-item|move-item|rename-item|"
        r"mkdir|md|ni|cp|mv|touch|tee|git\s+(add|commit|merge|rebase|pull|push|checkout|switch|apply)|"
        r"(?:npm|pnpm|yarn)\s+(install|uninstall|add|remove|update)|pip\s+(install|uninstall))\b|>{1,2}", re.I,
    )
    _PROCESS = re.compile(r"\b(start-process|start-job|invoke-command|ssh|docker|podman)\b", re.I)

    def __init__(self, restricted: bool = False) -> None:
        self.restricted = restricted
        self._confirmations: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _digest(command: str, cwd: str) -> str:
        return hashlib.sha256(f"{cwd}\0{command}".encode("utf-8")).hexdigest()

    def classify(self, command: str) -> CommandDecision:
        if not self.restricted:
            return CommandDecision(
                "terminal:unrestricted",
                "unrestricted",
                False,
                "Execução irrestrita habilitada pelo usuário.",
            )
        normalized = command.strip()
        for pattern, reason in self._DANGEROUS:
            if pattern.search(normalized):
                return CommandDecision("terminal:dangerous", "dangerous", True, reason)
        if self._WRITE.search(normalized):
            return CommandDecision("files:write", "elevated", True, "O comando pode modificar arquivos ou um repositório.")
        if self._PROCESS.search(normalized):
            return CommandDecision("process:execute", "elevated", True, "O comando pode iniciar outro processo ou sessão.")
        return CommandDecision("terminal:read-execute", "standard", False, "Comando de leitura ou execução comum.")

    def issue_confirmation(self, command: str, cwd: str) -> tuple[str, CommandDecision]:
        decision = self.classify(command)
        nonce = secrets.token_urlsafe(24)
        with self._lock:
            self._prune()
            self._confirmations[nonce] = (self._digest(command, cwd), time.time() + CONFIRMATION_TTL_SECONDS)
        return nonce, decision

    def consume_confirmation(self, nonce: str | None, command: str, cwd: str) -> bool:
        if not nonce:
            return False
        with self._lock:
            self._prune()
            record = self._confirmations.pop(str(nonce), None)
        return bool(record and record[0] == self._digest(command, cwd) and record[1] >= time.time())

    def _prune(self) -> None:
        now = time.time()
        self._confirmations = {key: value for key, value in self._confirmations.items() if value[1] >= now}
