"""Componentes sem hardware: estados, segmentação, métricas e entrega única."""
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
import time

import numpy as np


class Estado(Enum):
    AGUARDANDO_ATIVACAO = auto()
    PALAVRA_DE_ATIVACAO_DETECTADA = auto()
    ESCUTANDO_COMANDO = auto()
    PROCESSANDO_COMANDO = auto()
    RESPONDENDO = auto()
    AGUARDANDO_CONTINUACAO = auto()
    RECUPERANDO_ERRO = auto()
    ENCERRADO = auto()


class MaquinaEstados:
    TRANSICOES = {
        Estado.AGUARDANDO_ATIVACAO: {Estado.PALAVRA_DE_ATIVACAO_DETECTADA},
        Estado.PALAVRA_DE_ATIVACAO_DETECTADA: {Estado.ESCUTANDO_COMANDO, Estado.RESPONDENDO},
        Estado.ESCUTANDO_COMANDO: {Estado.PROCESSANDO_COMANDO, Estado.RESPONDENDO},
        Estado.PROCESSANDO_COMANDO: {Estado.RESPONDENDO, Estado.AGUARDANDO_CONTINUACAO},
        Estado.RESPONDENDO: {Estado.AGUARDANDO_CONTINUACAO, Estado.ESCUTANDO_COMANDO},
        Estado.AGUARDANDO_CONTINUACAO: {Estado.ESCUTANDO_COMANDO, Estado.RESPONDENDO},
        Estado.RECUPERANDO_ERRO: {Estado.ESCUTANDO_COMANDO},
        Estado.ENCERRADO: set(),
    }

    def __init__(self):
        self.estado = Estado.AGUARDANDO_ATIVACAO

    def mudar(self, novo):
        if novo == self.estado:
            return
        permitidos = self.TRANSICOES[self.estado]
        comuns = {Estado.RECUPERANDO_ERRO, Estado.AGUARDANDO_ATIVACAO, Estado.ENCERRADO}
        if self.estado == Estado.ENCERRADO or novo not in permitidos | comuns:
            raise RuntimeError(f"Transicao invalida: {self.estado.name} -> {novo.name}")
        self.estado = novo


class EntregaUnica:
    """IDs de captura, nunca igualdade de texto: permite repetir uma ordem real."""
    def __init__(self, limite=128):
        self.ids = deque(maxlen=limite)

    def aceitar(self, identificador):
        if identificador in self.ids:
            return False
        self.ids.append(identificador)
        return True


class Metricas:
    """Somente números em memória, sem áudio, texto ou chaves."""
    def __init__(self, limite=200):
        self.tempos = {}
        self.contadores = {}
        self.limite = limite
        self.fim_fala = None

    def contar(self, nome, quantidade=1):
        self.contadores[nome] = self.contadores.get(nome, 0) + quantidade

    def medir(self, nome, segundos):
        self.tempos.setdefault(nome, deque(maxlen=self.limite)).append(segundos)

    def resumo(self):
        return {"contadores": dict(self.contadores), "tempos_s": {
            nome: {"n": len(valores), "mediana": float(np.median(valores)),
                   "p95": float(np.percentile(valores, 95))}
            for nome, valores in self.tempos.items() if valores
        }}


@dataclass(frozen=True)
class Segmento:
    pcm: bytes
    motivo: str
    duracao: float
    fala_segundos: float


class Segmentador:
    """Relógio em amostras; conserva pausas e margens sem depender da CPU."""
    def __init__(self, taxa=16000, bloco_ms=20, pre_ms=500, inicio_ms=60,
                 silencio=0.85, maximo=20.0, minimo=0.12, silencio_curto=None,
                 frase_curta_ate=1.4):
        if not (0 < silencio < maximo <= 60 and 0 < bloco_ms <= 30):
            raise ValueError("Limites de segmentacao invalidos")
        if silencio_curto is not None and not (0 < silencio_curto <= silencio):
            raise ValueError("Silencio curto invalido")
        self.taxa, self.passo = taxa, bloco_ms / 1000
        self.tamanho = taxa * bloco_ms // 1000
        self.pre = deque(maxlen=max(1, pre_ms // bloco_ms))
        self.inicios = deque(maxlen=max(1, inicio_ms // bloco_ms))
        self.silencio, self.maximo, self.minimo = silencio, maximo, minimo
        self.silencio_curto = silencio if silencio_curto is None else silencio_curto
        self.frase_curta_ate = frase_curta_ate
        self.blocos = []
        self.ativo = False
        self.fala = self.pausa = self.duracao = 0.0
        self.finalizado = False

    def alimentar(self, pcm, fala):
        if self.finalizado:
            raise RuntimeError("Segmento ja entregue")
        if len(pcm) != self.tamanho * 2:
            raise ValueError("Bloco deve ser PCM16 mono no tamanho configurado")
        if not self.ativo:
            self.pre.append(pcm)
            self.inicios.append(bool(fala))
            if len(self.inicios) < self.inicios.maxlen or not all(self.inicios):
                return None
            self.ativo = True
            self.blocos.extend(self.pre)
            self.duracao = len(self.blocos) * self.passo
            self.fala = len(self.inicios) * self.passo
            return None
        self.blocos.append(pcm)
        self.duracao += self.passo
        if fala:
            self.fala += self.passo
            self.pausa = 0.0
        else:
            self.pausa += self.passo
        # Pausa depende do VAD; máximo é apenas o limite de segurança.
        motivo = "limite" if self.duracao >= self.maximo else "silencio"
        limite_pausa = self.silencio_curto if self.fala <= self.frase_curta_ate else self.silencio
        if motivo == "limite" or self.pausa + 1e-8 >= limite_pausa:
            self.finalizado = True
            return Segmento(b"".join(self.blocos), motivo, self.duracao, self.fala)
        return None


metricas = Metricas()
