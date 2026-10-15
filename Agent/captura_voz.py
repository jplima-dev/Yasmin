"""PortAudio produz blocos; ASR/rede nunca executam dentro do callback."""
from dataclasses import dataclass
from queue import Queue, Empty, Full
from math import gcd
import threading
import time

import numpy as np
from scipy.signal import resample_poly
import sounddevice as sd


class FalhaCaptura(OSError):
    pass


@dataclass(frozen=True)
class Bloco:
    pcm: bytes
    sequencia: int
    instante: float
    descontinuidade: bool = False


class CapturaContinua:
    def __init__(self, dispositivo, bloqueado=lambda: False, taxa=16000, bloco=320,
                 segundos_fila=2.0, taxa_entrada=None):
        self.dispositivo, self.bloqueado = dispositivo, bloqueado
        self.taxa, self.bloco = taxa, bloco
        self.taxa_entrada = int(taxa_entrada or taxa)
        self.bloco_entrada = round(bloco * self.taxa_entrada / taxa)
        self.fila = Queue(maxsize=max(1, int(segundos_fila * self.taxa_entrada /
                                            self.bloco_entrada)))
        self.stream = None
        self.sequencia = 0
        self.perdidos = 0
        self._ultimo = None
        self._fechado = threading.Event()

    def _callback(self, dados, frames, timing, status):
        self.sequencia += 1
        if self._fechado.is_set() or self.bloqueado():
            return
        item = Bloco(bytes(dados), self.sequencia, time.monotonic(),
                     bool(status) or frames != self.bloco_entrada
                     or len(dados) != self.bloco_entrada * 2)
        try:
            self.fila.put_nowait(item)
        except Full:
            self.perdidos += 1
            # Nunca espera o consumidor; o salto de sequência invalida a frase.
            try:
                self.fila.get_nowait()
            except Empty:
                pass
            try:
                self.fila.put_nowait(item)
            except Full:
                pass

    def iniciar(self):
        if self.stream is not None:
            return
        self._fechado.clear()
        try:
            sd.check_input_settings(device=self.dispositivo, channels=1,
                                    dtype="int16", samplerate=self.taxa_entrada)
            self.stream = sd.RawInputStream(
                device=self.dispositivo, samplerate=self.taxa_entrada, channels=1,
                dtype="int16", blocksize=self.bloco_entrada, callback=self._callback)
            self.stream.start()
        except (sd.PortAudioError, ValueError, OSError, RuntimeError) as erro:
            self.fechar()
            raise FalhaCaptura(f"Nao foi possivel abrir microfone PCM16/{self.taxa_entrada} Hz: {erro}") from erro

    def descartar(self):
        while True:
            try:
                self.fila.get_nowait()
            except Empty:
                break
        self._ultimo = None

    def ler(self, timeout=1.0):
        if self._fechado.is_set():
            raise FalhaCaptura("Captura encerrada")
        try:
            item = self.fila.get(timeout=timeout)
        except Empty as erro:
            raise FalhaCaptura("Microfone sem entregar amostras") from erro
        salto = self._ultimo is not None and item.sequencia != self._ultimo + 1
        self._ultimo = item.sequencia
        if item.descontinuidade or salto or time.monotonic() - item.instante > 2.0:
            raise FalhaCaptura("Amostras perdidas; frase descartada")
        if self.taxa_entrada == self.taxa:
            return item.pcm
        divisor = gcd(self.taxa_entrada, self.taxa)
        amostras = np.frombuffer(item.pcm, dtype="<i2")
        convertidas = resample_poly(amostras.astype(np.float32), self.taxa // divisor,
                                    self.taxa_entrada // divisor, padtype="line")
        if len(convertidas) != self.bloco:
            raise FalhaCaptura("Conversao da taxa de audio entregou bloco incompleto")
        return np.clip(np.rint(convertidas), -32768, 32767).astype("<i2").tobytes()

    def fechar(self):
        self._fechado.set()
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.abort()
            except (sd.PortAudioError, OSError, RuntimeError):
                pass
            try:
                stream.close()
            except (sd.PortAudioError, OSError, RuntimeError):
                pass
        self.descartar()
