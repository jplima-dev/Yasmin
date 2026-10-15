"""Regressoes de audio/voz sem rede, microfone, alto-falante ou modelos reais."""

import importlib
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch
import wave

import numpy as np


BASE = Path(__file__).resolve().parents[1] / "Agent"
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

with patch.dict(os.environ, {"YASM_VOICE_SERVER": "1"}):
    voz = importlib.import_module("voz_yasm")
    audio = importlib.import_module("audio_yasm")
    servidor = importlib.import_module("servicos.voz_neural_server")
    configuracao_voz = importlib.import_module("interface.config_inicial")


def escrever_wav(caminho):
    with wave.open(str(caminho), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(np.array([0, 100, -100, 0], dtype=np.int16).tobytes())


class AudioTests(unittest.TestCase):
    def test_captura_tenta_dispositivo_e_taxa_nativa_quando_padrao_falha(self):
        class CapturaFalsa:
            def __init__(self, dispositivo, bloqueado, taxa_entrada):
                self.dispositivo = dispositivo
                self.taxa_entrada = taxa_entrada
                self.stream = None

            def iniciar(self):
                if (self.dispositivo, self.taxa_entrada) != (1, 48000):
                    raise audio.FalhaCaptura("formato indisponível")
                self.stream = object()

        dispositivos = [
            {"name": "Padrão", "max_input_channels": 1, "default_samplerate": 44100},
            {"name": "USB", "max_input_channels": 1, "default_samplerate": 48000},
        ]
        with patch.object(audio, "_captura", None), patch.object(audio, "_erro_captura", None), patch.object(
            audio, "CapturaContinua", CapturaFalsa
        ), patch.object(audio.sd, "query_devices", return_value=dispositivos), patch.object(
            audio.sd, "default", types.SimpleNamespace(device=(0, 0))
        ), patch.dict(os.environ, {"YASM_AUDIO_DEVICE": ""}):
            captura = audio.obter_captura()
            self.assertEqual((captura.dispositivo, captura.taxa_entrada), (1, 48000))
            self.assertEqual(audio.estado_captura(), {"disponivel": True, "erro": None})

    def test_calibracao_reutiliza_fluxo_continuo(self):
        captura = Mock()
        captura.ler.return_value = np.zeros(audio.BLOCO, dtype="<i2").tobytes()
        with patch.object(audio, "obter_captura", return_value=captura), patch.object(
            audio.voz, "aguardar_microfone"
        ), patch.object(audio.sd, "rec", side_effect=AssertionError("nao abrir outra gravacao")):
            audio.calibrar_sounddevice(duracao=0.04)
        captura.descartar.assert_called_once()
        self.assertEqual(captura.ler.call_count, 2)

    def test_nome_do_microfone_tenta_todas_as_interfaces_correspondentes(self):
        dispositivos = [
            {"name": "USB Microphone MME", "max_input_channels": 1,
             "default_samplerate": 44100},
            {"name": "USB Microphone WASAPI", "max_input_channels": 1,
             "default_samplerate": 48000},
        ]
        with patch.dict(os.environ, {"YASM_AUDIO_DEVICE": "USB Microphone"}), patch.object(
            audio.sd, "query_devices", return_value=dispositivos
        ), patch.object(audio.sd, "default", types.SimpleNamespace(device=(0, 0))):
            self.assertEqual(list(audio._candidatos_captura()),
                             [(0, 16000), (0, 44100), (1, 16000), (1, 48000)])

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
        with patch.object(audio, "ASR_FALLBACK", "vosk"), patch.object(audio, "RECONHECIMENTO_ONLINE", True), patch.object(
            audio, "gravar_com_sounddevice", return_value=object()
        ), patch.object(audio, "_google", side_effect=audio.sr.RequestError("offline")), patch.object(
            audio, "_vosk", return_value="abrir calculadora"
        ):
            self.assertEqual(audio.escutar(), "abrir calculadora")

    def test_google_padrao_nao_carrega_vosk(self):
        with patch.object(audio, "WAKE_MOTOR", "google"), patch.object(audio, "ASR_MOTOR", "google"), patch.object(
            audio, "ASR_FALLBACK", "nenhum"
        ), patch.object(audio, "_carregar_vosk", side_effect=AssertionError("Vosk carregado")), patch.object(
            audio, "_vad_atual"
        ), patch.object(audio, "_preparado", False):
            self.assertTrue(audio.preparar_reconhecimento())

    def test_ganho_moderado_eleva_voz_baixa_sem_distorcer(self):
        baixo = np.tile(np.array([-300, 300], dtype=np.int16), 160)
        tratado = audio._normalizar_audio([baixo])
        self.assertGreater(audio._rms(tratado), audio._rms(baixo))
        self.assertLessEqual(audio._rms(tratado), audio._rms(baixo) * audio.AGC_MAX + 1)
        alto = np.tile(np.array([-16000, 16000], dtype=np.int16), 160)
        np.testing.assert_array_equal(audio._normalizar_audio([alto]), alto)


class VozTests(unittest.TestCase):
    def test_aquecimento_explicitamente_iniciado_uma_vez(self):
        with patch.dict(os.environ, {"YASM_VOICE_SERVER": "0"}), patch.object(
            voz, "_aquecimento_iniciado", False
        ), patch.object(voz.threading, "Thread") as thread:
            voz.aquecer_motor_em_segundo_plano()
            voz.aquecer_motor_em_segundo_plano()
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()

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

    def test_resposta_longa_inicia_com_trecho_curto(self):
        texto = " ".join(["palavra"] * 100)
        partes = voz._blocos_resposta_rapida(texto)
        self.assertGreater(len(partes), 1)
        self.assertLessEqual(len(partes[0]), 220)
        self.assertTrue(all(len(parte) <= 220 for parte in partes[1:]))
        self.assertEqual(" ".join(partes), texto)

    def test_frase_curta_completa_nao_e_dividida(self):
        texto = "Consegui terminar essa etapa e agora podemos revisar com calma o resultado antes de seguir"
        self.assertEqual(voz._blocos_resposta_rapida(texto), [texto])

    def test_palavra_extensa_nao_atrasa_primeira_fala(self):
        partes = voz._blocos_resposta_rapida("x" * 1000 + " fim")
        self.assertLessEqual(len(partes[0]), 80)

    def test_proximo_trecho_sintetiza_durante_reproducao(self):
        proximo_iniciado = threading.Event()
        reproduzidos = []

        def preparar(bloco):
            if bloco == "segundo":
                proximo_iniciado.set()
            return self.cache / f"{bloco}.wav", True, True, 0.01

        def reproduzir(caminho, flags):
            if not reproduzidos:
                self.assertTrue(proximo_iniciado.wait(1))
            reproduzidos.append(caminho)

        som = types.SimpleNamespace(SND_FILENAME=1, SND_NODEFAULT=2, PlaySound=reproduzir)
        with patch.object(voz, "_blocos_resposta_rapida", return_value=["primeiro", "segundo"]), patch.object(
            voz, "_preparar_bloco", side_effect=preparar
        ), patch.object(voz, "winsound", som), patch.object(voz, "CACHE_VOZ", True):
            self.assertTrue(voz._falar_serializado("resposta"))
        self.assertEqual(len(reproduzidos), 2)

    def test_palavra_muito_longa_tambem_respeita_limite(self):
        partes = voz._dividir_texto("x" * 1000, 420)
        self.assertEqual("".join(partes), "x" * 1000)
        self.assertTrue(all(len(parte) <= 420 for parte in partes))

    def test_voz_temporaria_antiga_recebe_migracao(self):
        with patch.object(voz, "_voz_temporaria", "pt-BR-FranciscaNeural"):
            self.assertEqual(voz.obter_voz_atual(), "kitsune:emilia")

    def test_vozes_disponiveis_correspondem_as_amostras_e_ao_modelo(self):
        self.assertEqual(voz.vozes_com_amostra(),
                         ("kitsune:emilia", "kitsune:frieren", "kitsune:violet"))
        self.assertIsNone(voz._arquivo_amostra("kitsune:../../outro"))

    def test_previa_toca_amostra_float32_convertida_para_pcm16(self):
        original = BASE / "amostras_voz" / "frieren.wav"
        tamanho = original.stat().st_size

        def conferir(caminho, flags):
            with wave.open(caminho, "rb") as wav:
                self.assertEqual(wav.getsampwidth(), 2)
                self.assertEqual(wav.getframerate(), 22050)
                self.assertGreater(wav.getnframes(), 0)

        som = types.SimpleNamespace(SND_FILENAME=1, SND_NODEFAULT=2,
                                    PlaySound=Mock(side_effect=conferir))
        with patch.object(voz, "winsound", som):
            self.assertTrue(voz.reproduzir_amostra("kitsune:frieren"))
        som.PlaySound.assert_called_once()
        self.assertEqual(original.stat().st_size, tamanho)

    def test_escolha_inicial_usa_amostras_reais(self):
        self.assertEqual(tuple(item["id"] for item in configuracao_voz.OPCOES_VOZ.values()),
                         voz.vozes_com_amostra())
        with patch.object(voz, "definir_voz_temporaria") as selecionar, patch.object(
            voz, "reproduzir_amostra", return_value=True
        ) as tocar, patch.object(configuracao_voz, "falar") as sintetizar:
            configuracao_voz.testar_voz("2")
        selecionar.assert_called_once_with("kitsune:frieren")
        tocar.assert_called_once_with("kitsune:frieren")
        sintetizar.assert_not_called()

    def test_voz_escolhida_persiste_o_speaker_da_amostra(self):
        with patch.object(configuracao_voz, "falar"), patch.object(
            configuracao_voz, "testar_voz"
        ), patch.object(configuracao_voz, "perguntar_opcao", return_value="2"), patch.object(
            voz, "definir_voz"
        ) as persistir:
            self.assertEqual(configuracao_voz.escolher_voz(), "kitsune:frieren")
        persistir.assert_called_once_with("kitsune:frieren")

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

    def test_indicador_visual_acompanha_reproducao_real(self):
        arquivo = self.cache / "fala.wav"
        escrever_wav(arquivo)
        durante = []
        som = types.SimpleNamespace(SND_FILENAME=1, SND_NODEFAULT=2,
                                    PlaySound=Mock(side_effect=lambda *_: durante.append(voz.falando())))
        with patch.object(voz, "_arquivo_cache", return_value=arquivo), patch.object(
            voz, "winsound", som
        ):
            self.assertTrue(voz.falar("Olá"))
        self.assertEqual(durante, [True])
        self.assertTrue(voz.falando())
        with patch.object(voz, "_fim_reproducao", voz.time.monotonic() - 1):
            self.assertFalse(voz.falando())

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
