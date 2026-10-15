"""Regressoes de audio/voz sem rede, microfone, alto-falante ou modelos reais."""

import importlib
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import wave

import numpy as np


BASE = Path(__file__).resolve().parents[1] / "yasmin_certo"
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

with patch.dict(os.environ, {"YASM_VOICE_SERVER": "1"}):
    voz = importlib.import_module("voz_yasm")
    audio = importlib.import_module("audio_yasm")
    servidor = importlib.import_module("servicos.voz_neural_server")


def escrever_wav(caminho):
    with wave.open(str(caminho), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(np.array([0, 100, -100, 0], dtype=np.int16).tobytes())


class AudioTests(unittest.TestCase):
    def test_ruido_int16_minimo_nao_vira_volume_maximo(self):
        amostras = np.array([-1, 1] * 160, dtype=np.int16)
        self.assertAlmostEqual(audio._rms(amostras), 1.0)
        self.assertLess(np.max(np.abs(audio._audio_float(amostras))), 0.0001)

    def test_float_e_int16_equivalentes(self):
        amostras = np.array([-16384, 16384], dtype=np.int16)
        np.testing.assert_allclose(
            audio._audio_float(amostras),
            audio._audio_float(amostras.astype(np.float32) / 32768),
        )

    def test_nan_nao_contamina_vad(self):
        resultado = audio._audio_float(np.array([np.nan, np.inf, 0.1, -0.1]))
        self.assertTrue(np.isfinite(resultado).all())
        np.testing.assert_allclose(resultado, [0, 0, 0.1, -0.1])

    def test_microfone_escolhido_funciona_sem_microfone_padrao(self):
        def consultar(dispositivo=None, **kwargs):
            if "kind" in kwargs:
                raise RuntimeError("sem dispositivo padrao")
            self.assertEqual(dispositivo, 3)
            return {"name": "USB"}

        with patch.object(audio, "_dispositivo_entrada", return_value=3), patch.object(
            audio.sd, "query_devices", side_effect=consultar
        ):
            self.assertEqual(audio.diagnostico_audio(), "microfone selecionado: USB")

    def test_google_tem_timeout_de_rede(self):
        reconhecedor = Mock()
        with patch.object(audio.sr, "Recognizer", return_value=reconhecedor):
            audio._google(object())
        self.assertEqual(reconhecedor.operation_timeout, audio.TIMEOUT_INTERNET)

    def test_modelo_vosk_corrompido_nao_destroi_inicializacao(self):
        with patch.object(audio, "_modelo_vosk", None), patch.object(
            audio, "_aviso_modelo", False
        ), patch.object(audio, "MODELO_VOSK_DIR", BASE), patch.object(
            audio, "Model", side_effect=RuntimeError("modelo invalido")
        ), patch.object(audio, "SetLogLevel", None):
            self.assertIsNone(audio._carregar_vosk())

    def test_transcricao_vazia_nao_reinicia_espera_infinitamente(self):
        with patch.object(audio, "RECONHECIMENTO_ONLINE", False), patch.object(
            audio, "gravar_com_sounddevice", return_value=object()
        ) as gravar, patch.object(audio, "_vosk", return_value=""):
            self.assertEqual(audio.escutar(timeout=0.5), "")
            gravar.assert_called_once()

    def test_falha_google_usa_vosk(self):
        with patch.object(audio, "RECONHECIMENTO_ONLINE", True), patch.object(
            audio, "gravar_com_sounddevice", return_value=object()
        ), patch.object(audio, "_google", side_effect=audio.sr.RequestError("offline")), patch.object(
            audio, "_vosk", return_value="abrir calculadora"
        ):
            self.assertEqual(audio.escutar(), "abrir calculadora")


class VozTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.cache = Path(self.pasta.name)
        alteracao = patch.object(voz, "_CACHE_DIR", self.cache)
        alteracao.start()
        self.addCleanup(alteracao.stop)

    def test_frase_sem_pontuacao_respeita_limite(self):
        texto = " ".join(["palavra"] * 500)
        partes = voz._dividir_texto(texto)
        self.assertTrue(all(0 < len(parte) <= 420 for parte in partes))
        self.assertEqual(" ".join(partes), texto)

    def test_palavra_muito_longa_tambem_respeita_limite(self):
        partes = voz._dividir_texto("x" * 1000, 420)
        self.assertEqual("".join(partes), "x" * 1000)
        self.assertTrue(all(len(parte) <= 420 for parte in partes))

    def test_voz_temporaria_antiga_recebe_migracao(self):
        with patch.object(voz, "_voz_temporaria", "pt-BR-FranciscaNeural"):
            self.assertEqual(voz.obter_voz_atual(), "kitsune:emilia")

    def test_cache_corrompido_e_truncado_e_rejeitado(self):
        arquivo = self.cache / "corrompido.wav"
        arquivo.write_bytes(b"x" * 100)
        self.assertFalse(voz._wav_valido(arquivo))
        escrever_wav(arquivo)
        self.assertTrue(voz._wav_valido(arquivo))
        arquivo.write_bytes(arquivo.read_bytes()[:-2])
        self.assertFalse(voz._wav_valido(arquivo))

    def test_cache_corrompido_e_regenerado_antes_de_reproduzir(self):
        arquivo = self.cache / "fala.wav"
        arquivo.write_bytes(b"x" * 100)

        def gerar(texto, destino):
            escrever_wav(destino)
            return True

        with patch.object(voz, "_arquivo_cache", return_value=arquivo), patch.object(
            voz, "_gerar_wav_offline", side_effect=gerar
        ) as sintetizar, patch.object(voz, "winsound", Mock(SND_FILENAME=1, SND_NODEFAULT=2)):
            self.assertTrue(voz.falar("Ola"))
            sintetizar.assert_called_once_with("Ola", arquivo)

    def test_kitsune_grava_pcm_sem_deixar_temporarios(self):
        sintetizador = types.SimpleNamespace(
            synthesize=Mock(return_value=np.array([-1.5, -0.25, 0.25, 1.5], dtype=np.float32)),
            sample_rate=24000,
        )
        arquivo = self.cache / "neural.wav"
        with patch.object(voz, "_carregar_kitsune", return_value=sintetizador):
            self.assertTrue(voz._gerar_wav_kitsune("ola", arquivo, "kitsune:emilia"))
        with wave.open(str(arquivo), "rb") as wav:
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.getframerate(), 24000)
            amostras = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
        np.testing.assert_array_equal(amostras, [-32768, -8192, 8192, 32767])
        self.assertEqual(list(self.cache.iterdir()), [arquivo])

    def test_sintese_interrompida_preserva_cache_anterior(self):
        arquivo = self.cache / "neural.wav"
        escrever_wav(arquivo)
        anterior = arquivo.read_bytes()
        sintetizador = types.SimpleNamespace(
            synthesize=Mock(return_value=np.zeros(100, dtype=np.float32)), sample_rate=16000,
        )

        def falhar(destino, taxa, amostras):
            Path(destino).write_bytes(b"parcial")
            raise OSError("gravacao interrompida")

        with patch.object(voz, "_carregar_kitsune", return_value=sintetizador), patch(
            "scipy.io.wavfile.write", side_effect=falhar
        ), self.assertRaises(OSError):
            voz._gerar_wav_kitsune("ola", arquivo, "kitsune:emilia")
        self.assertEqual(arquivo.read_bytes(), anterior)
        self.assertEqual(list(self.cache.iterdir()), [arquivo])

    def test_resposta_servidor_com_tipo_errado_usa_reserva(self):
        cliente = Mock()
        cliente.recv.return_value = b"[]\n"
        conexao = Mock()
        conexao.__enter__ = Mock(return_value=cliente)
        conexao.__exit__ = Mock(return_value=False)
        with patch.object(voz.socket, "create_connection", return_value=conexao):
            self.assertFalse(voz._gerar_via_servico("ola", self.cache / "fala.wav", "kitsune:emilia"))

    def test_sintese_neural_vazia_tenta_voz_windows(self):
        arquivo = self.cache / "fala.wav"
        with patch.object(voz, "obter_voz_atual", return_value="kitsune:emilia"), patch.object(
            voz, "_gerar_via_servico", return_value=False
        ), patch.object(voz, "_gerar_wav_kitsune", return_value=False), patch.object(
            voz.subprocess, "run", return_value=types.SimpleNamespace(returncode=1)
        ) as executar:
            self.assertFalse(voz._gerar_wav_offline("ola", arquivo))
            executar.assert_called_once()
        self.assertEqual(list(self.cache.iterdir()), [])


class ServidorTests(unittest.TestCase):
    def test_payload_com_tipo_errado_e_rejeitado(self):
        for payload in ([], None, "texto", {"texto": None}, {"texto": "ola", "arquivo": []}):
            with self.subTest(payload=payload):
                self.assertFalse(servidor._processar(payload)["ok"])

    def test_arquivo_fora_do_cache_nao_e_escrito(self):
        with patch.object(servidor.voz, "_gerar_wav_kitsune") as gerar:
            resultado = servidor._processar({
                "texto": "ola", "voz": "kitsune:emilia", "arquivo": str(BASE / "fora.wav")
            })
            self.assertFalse(resultado["ok"])
            gerar.assert_not_called()

    def test_linha_fragmentada_e_lida(self):
        conexao = Mock()
        conexao.recv.side_effect = [b'{"acao":', b'"ping"}\n']
        self.assertEqual(servidor._receber_linha(conexao), b'{"acao":"ping"}')

    def test_pedido_grande_e_rejeitado(self):
        conexao = Mock()
        conexao.recv.side_effect = lambda limite: b"x" * limite
        with patch.object(servidor, "LIMITE_PEDIDO", 8), self.assertRaises(ValueError):
            servidor._receber_linha(conexao)

    def test_pedido_sem_delimitador_e_rejeitado(self):
        conexao = Mock()
        conexao.recv.side_effect = [b'{"acao":"ping"}', b""]
        with self.assertRaises(ValueError):
            servidor._receber_linha(conexao)


if __name__ == "__main__":
    unittest.main()
