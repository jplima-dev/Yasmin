"""Verifica se algum microfone realmente entrega áudio, sem salvar a gravação."""

from __future__ import annotations

import numpy as np

import audio_yasm as audio
from captura_voz import CapturaContinua, FalhaCaptura


def main() -> int:
    print("Testando entradas de áudio. Fale perto do microfone durante o teste.")
    try:
        candidatos = list(audio._candidatos_captura())
    except FalhaCaptura as erro:
        print(f"Falha ao listar dispositivos: {erro}")
        return 1
    if not candidatos:
        print("Nenhum dispositivo de entrada foi encontrado pelo Windows.")
        return 1

    falhas = []
    for dispositivo, taxa in candidatos:
        captura = CapturaContinua(dispositivo, taxa_entrada=taxa)
        try:
            captura.iniciar()
            blocos = [captura.ler(timeout=1.5) for _ in range(25)]
            amostras = np.frombuffer(b"".join(blocos), dtype="<i2").astype(np.float32)
            rms = float(np.sqrt(np.mean(amostras * amostras)))
            nome = audio.sd.query_devices(dispositivo).get("name", str(dispositivo))
            print(f"Entrada funcional: {dispositivo} · {nome} · {taxa} Hz · nível RMS {rms:.0f}")
            if rms < 15:
                print("O fluxo abriu, mas quase não há sinal. Confira mute e nível de entrada no Windows.")
            print(f"Para fixar este dispositivo: $env:YASM_AUDIO_DEVICE='{dispositivo}'")
            return 0
        except (FalhaCaptura, audio.sd.PortAudioError) as erro:
            falhas.append(f"{dispositivo}/{taxa} Hz: {str(erro).split(' [PaErrorCode', 1)[0]}")
        finally:
            captura.fechar()
    print(f"Nenhuma das {len(candidatos)} combinações entregou áudio.")
    for falha in falhas[:3]:
        print("- " + falha)
    print("Confira conexão, driver e permissão de microfone para aplicativos de desktop no Windows.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
