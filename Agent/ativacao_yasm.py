"""Ativação local. Vosk é uma reserva lexical, não um wake model treinado."""
from collections import deque
import json
import os
from pathlib import Path

import numpy as np

from config_yasm import opcao_numero
from util_yasm import normalizar, VARIACOES_YASM


PREFIXOS = {"oi", "ola", "ei", "hey", "iniciar", "inicia", "ligar", "liga",
            "abrir", "abre", "ativar", "ativa"}


def chamada_exata(texto):
    palavras = normalizar(texto).split()
    if palavras and palavras[0] in PREFIXOS:
        palavras = palavras[1:]
    return bool(palavras and palavras[0] in VARIACOES_YASM)


def remover_prefixo(texto):
    # Preserva pontuação e operadores do comando reconhecido.
    import re
    partes = list(re.finditer(r"\w+", texto))
    if not partes:
        return texto
    indice = 1 if normalizar(partes[0].group()) in PREFIXOS else 0
    if indice < len(partes) and normalizar(partes[indice].group()) in VARIACOES_YASM:
        return texto[partes[indice].end():].lstrip(" ,.!?:;")
    return texto


class VoskAtivacao:
    def __init__(self, modelo, recognizer_factory):
        self.modelo, self.factory = modelo, recognizer_factory
        self.minimo = opcao_numero("YASM_WAKE_CONFIANCA", 0.75, 0, 1)
        self.estabilidade = int(opcao_numero("YASM_WAKE_ESTABILIDADE", 3, 1, 10))
        self.vocabulario = [p for p in sorted(VARIACOES_YASM)
                           if modelo.vosk_model_find_word(p) >= 0]
        if not self.vocabulario:
            raise RuntimeError("Modelo Vosk sem aliases da Yasm; configure outro detector")
        self.reset()

    def reset(self):
        self.rec = self.factory(self.modelo, 16000)
        self.rec.SetWords(True)
        self.rec.SetPartialWords(True)
        self.contagem = self.amostras = 0
        self.ultimo = ""
        self.parciais = deque(maxlen=self.estabilidade)

    def alimentar(self, pcm):
        self.amostras += len(pcm) // 2
        final = self.rec.AcceptWaveform(pcm)
        resultado = json.loads(self.rec.Result() if final else self.rec.PartialResult())
        texto = resultado.get("text" if final else "partial", "")
        palavras = resultado.get("result" if final else "partial_result", [])
        chamadas = [p for p in palavras if p.get("word") in self.vocabulario]
        confiavel = any(float(p.get("conf", 0)) >= self.minimo for p in chamadas)
        candidato = chamada_exata(texto) and confiavel
        self.parciais.append(candidato)
        detectou = candidato and (final or (
            len(self.parciais) == self.estabilidade and all(self.parciais)))
        if final or self.amostras >= 16000 * 12:
            self.reset()
        return detectou

    def fechar(self):
        self.rec = None


class PorcupineAtivacao:
    def __init__(self):
        import pvporcupine
        keyword = Path(os.environ.get("YASM_PORCUPINE_KEYWORD", ""))
        modelo = Path(os.environ.get("YASM_PORCUPINE_MODEL", ""))
        chave = os.environ.get("PICOVOICE_ACCESS_KEY", "")
        if not chave or not keyword.is_file() or not modelo.is_file():
            raise ValueError("Porcupine exige AccessKey, .ppn personalizado e .pv portugues")
        self.motor = pvporcupine.create(
            access_key=chave, keyword_paths=[str(keyword)], model_path=str(modelo),
            sensitivities=[opcao_numero("YASM_WAKE_SENSIBILIDADE", 0.5, 0, 1)])
        if self.motor.sample_rate != 16000:
            self.motor.delete()
            raise ValueError("Porcupine requer taxa diferente de 16 kHz")
        self.pendente = bytearray()

    def reset(self):
        # Alimenta silêncio para eliminar contexto acústico entre conversas.
        self.pendente.clear()
        for _ in range(16000 * 2 // self.motor.frame_length + 1):
            self.motor.process([0] * self.motor.frame_length)

    def alimentar(self, pcm):
        self.pendente.extend(pcm)
        tamanho = self.motor.frame_length * 2
        detectou = False
        while len(self.pendente) >= tamanho:
            frame = bytes(self.pendente[:tamanho])
            del self.pendente[:tamanho]
            detectou |= self.motor.process(np.frombuffer(frame, dtype="<i2").tolist()) >= 0
        return detectou

    def fechar(self):
        self.motor.delete()
