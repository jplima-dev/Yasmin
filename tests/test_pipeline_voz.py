"""Contratos de áudio com sinais sintéticos, sem medir precisão linguística."""
import copy
import importlib
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

import numpy as np

BASE = Path(__file__).resolve().parents[1] / "Agent"
sys.path.insert(0, str(BASE))
with patch.dict(os.environ, {"YASM_VOICE_SERVER": "1"}):
    import audio_yasm as audio
    import voz_yasm as voz
    import yas
    import ia_yasm
    import memoria_yasm as memoria
from pipeline_voz import Segmentador, Estado, MaquinaEstados, EntregaUnica, Metricas
from captura_voz import CapturaContinua, FalhaCaptura
from ativacao_yasm import chamada_exata, remover_prefixo, VoskAtivacao, PorcupineAtivacao

SILENCIO = bytes(640)
SOM = np.tile(np.array([-200, 200], dtype="<i2"), 160).tobytes()


class SegmentacaoTests(unittest.TestCase):
    def segmento(self, flags, **kwargs):
        s = Segmentador(**kwargs)
        resultado = None
        for flag in flags:
            resultado = s.alimentar(SOM if flag else SILENCIO, flag)
            if resultado:
                break
        return s, resultado

    def test_silencio_ilimitado_tem_memoria_limitada(self):
        s, resultado = self.segmento([False] * 10000)
        self.assertIsNone(resultado)
        self.assertEqual(len(s.pre), 25)
        self.assertEqual(s.blocos, [])

    def test_pre_e_pos_fala_preservados(self):
        s, resultado = self.segmento([False] * 10 + [True] * 20 + [False] * 43)
        self.assertTrue(resultado.pcm.startswith(SILENCIO * 10 + SOM))
        self.assertTrue(resultado.pcm.endswith(SILENCIO * 43))
        self.assertEqual(resultado.motivo, "silencio")

    def test_pausa_natural_nao_corta(self):
        s, resultado = self.segmento([True] * 20 + [False] * 30 + [True] * 20 + [False] * 43)
        self.assertIsNotNone(resultado)
        self.assertGreater(resultado.duracao, 2)
        self.assertAlmostEqual(resultado.fala_segundos, 0.8)

    def test_frase_curta_termina_apos_pausa_curta(self):
        _, resultado = self.segmento([True] * 20 + [False] * 20,
                                     silencio=0.65, silencio_curto=0.4)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado.motivo, "silencio")

    def test_frase_longa_preserva_pausa_natural(self):
        segmentador = Segmentador(silencio=0.65, silencio_curto=0.4)
        for flag in [True] * 100 + [False] * 20:
            self.assertIsNone(segmentador.alimentar(SOM if flag else SILENCIO, flag))
        for _ in range(12):
            self.assertIsNone(segmentador.alimentar(SILENCIO, False))
        self.assertIsNotNone(segmentador.alimentar(SILENCIO, False))

    def test_limite_duro_para_fala_continua(self):
        s, resultado = self.segmento([True] * 2000, maximo=2)
        self.assertEqual(resultado.motivo, "limite")
        self.assertLessEqual(len(resultado.pcm), 2 * 16000 * 2 + 640)

    def test_ruido_impulsivo_nao_inicia(self):
        s, resultado = self.segmento([True, False] * 200)
        self.assertFalse(s.ativo)

    def test_segmento_nao_entrega_duas_vezes(self):
        s, resultado = self.segmento([True] * 10 + [False] * 50)
        with self.assertRaises(RuntimeError):
            s.alimentar(SOM, True)

    def test_bloco_invalido_e_rejeitado(self):
        with self.assertRaises(ValueError):
            Segmentador().alimentar(bytes(100), True)

    def test_fala_lenta_maior_que_cinco_segundos(self):
        _, resultado = self.segmento([True] * 350 + [False] * 43)
        self.assertEqual(resultado.motivo, "silencio")
        self.assertGreater(resultado.duracao, 7)


class CapturaTests(unittest.TestCase):
    def test_taxa_nativa_48khz_e_convertida_em_blocos_de_16khz(self):
        captura = CapturaContinua(9, taxa_entrada=48000)
        amostras = (np.sin(2 * np.pi * 440 * np.arange(960) / 48000) * 8000).astype("<i2")
        captura._callback(amostras.tobytes(), 960, None, False)
        convertido = np.frombuffer(captura.ler(), dtype="<i2")
        self.assertEqual(len(convertido), 320)
        self.assertGreater(np.max(np.abs(convertido)), 5000)

    def test_callback_limitado_e_overflow_invalida_frase(self):
        c = CapturaContinua(None, segundos_fila=0.04)
        c._callback(SOM, 320, None, False)
        c.ler()
        for _ in range(5):
            c._callback(SOM, 320, None, False)
        self.assertEqual(c.fila.qsize(), 2)
        self.assertEqual(c.perdidos, 3)
        with self.assertRaises(FalhaCaptura):
            c.ler()

    def test_overflow_portaudio_e_rejeitado(self):
        c = CapturaContinua(None)
        c._callback(SOM, 320, None, True)
        with self.assertRaises(FalhaCaptura):
            c.ler()

    def test_bloco_truncado_e_rejeitado(self):
        c = CapturaContinua(None)
        c._callback(SOM[:100], 320, None, False)
        with self.assertRaises(FalhaCaptura):
            c.ler()

    def test_voz_da_assistente_nao_entra_na_fila(self):
        c = CapturaContinua(None, bloqueado=lambda: True)
        c._callback(SOM, 320, None, False)
        self.assertEqual(c.fila.qsize(), 0)

    def test_dispositivo_parou_de_entregar(self):
        with self.assertRaises(FalhaCaptura):
            CapturaContinua(None).ler(timeout=0.001)

    def test_libera_stream_quando_start_falha(self):
        stream = Mock()
        stream.start.side_effect = OSError("desconectado")
        with patch("captura_voz.sd.check_input_settings"), patch(
            "captura_voz.sd.RawInputStream", return_value=stream
        ), self.assertRaises(FalhaCaptura):
            CapturaContinua(1).iniciar()
        stream.close.assert_called_once()

    def test_falha_ao_liberar_stream_nao_mascara_erro_de_captura(self):
        stream = Mock()
        stream.start.side_effect = RuntimeError("driver falhou")
        stream.abort.side_effect = OSError("abort indisponivel")
        with patch("captura_voz.sd.check_input_settings"), patch(
            "captura_voz.sd.RawInputStream", return_value=stream
        ), self.assertRaises(FalhaCaptura):
            CapturaContinua(1).iniciar()
        stream.close.assert_called_once()

    def test_recuperacao_limitada(self):
        operacao = Mock(side_effect=FalhaCaptura())
        with patch.object(audio, "fechar_captura"), patch.object(audio.time, "sleep") as dormir:
            with self.assertRaises(FalhaCaptura):
                audio.recuperar_captura(operacao)
        self.assertEqual(operacao.call_count, 3)
        self.assertEqual([x.args[0] for x in dormir.call_args_list], [0.25, 0.5])

    def test_recuperacao_apos_desconexao(self):
        operacao = Mock(side_effect=[FalhaCaptura(), "recuperado"])
        with patch.object(audio, "fechar_captura"), patch.object(audio.time, "sleep"):
            self.assertEqual(audio.recuperar_captura(operacao), "recuperado")

    def test_microfone_inexistente_nao_cai_no_padrao(self):
        with patch.dict(os.environ, {"YASM_AUDIO_DEVICE": "inexistente"}), patch.object(
            audio.sd, "query_devices", return_value=[]
        ), self.assertRaises(FalhaCaptura):
            audio._dispositivo_entrada()


class AtivacaoTests(unittest.TestCase):
    def test_nome_so_no_inicio_ou_apos_saudacao(self):
        for texto in ["Yasmin, abra o navegador", "ei Yasm", "iniciar Yasm", "jasmim"]:
            self.assertTrue(chamada_exata(texto), texto)
        for texto in ["ontem a yasmin chegou", "yasuo", "asma", "mais", ""]:
            self.assertFalse(chamada_exata(texto), texto)

    def test_retirar_chamada_preserva_operadores(self):
        self.assertEqual(remover_prefixo("Ei Yasm, calcule 2 + 3!"), "calcule 2 + 3!")

    def test_modelo_sem_vocabulario_falha_explicitamente(self):
        modelo = Mock()
        modelo.vosk_model_find_word.return_value = -1
        with self.assertRaises(RuntimeError):
            VoskAtivacao(modelo, Mock())

    def test_vosk_exige_estabilidade_e_confianca(self):
        modelo, rec = Mock(), Mock()
        modelo.vosk_model_find_word.side_effect = lambda p: 1 if p == "yasmin" else -1
        rec.AcceptWaveform.return_value = False
        rec.PartialResult.return_value = '{"partial":"yasmin","partial_result":[{"word":"yasmin","conf":0.9}]}'
        with patch.dict(os.environ, {"YASM_WAKE_ESTABILIDADE": "3"}):
            detector = VoskAtivacao(modelo, Mock(return_value=rec))
        self.assertFalse(detector.alimentar(SOM))
        self.assertFalse(detector.alimentar(SOM))
        self.assertTrue(detector.alimentar(SOM))
        rec.PartialResult.return_value = '{"partial":"yasmin","partial_result":[{"word":"yasmin","conf":0.3}]}'
        self.assertFalse(detector.alimentar(SOM))

    def test_porcupine_remonta_frames_sem_perder_amostras(self):
        motor = Mock(sample_rate=16000, frame_length=512)
        motor.process.return_value = -1
        with tempfile.TemporaryDirectory() as pasta:
            ppn, pv = Path(pasta) / "yasm.ppn", Path(pasta) / "pt.pv"
            ppn.touch(); pv.touch()
            with patch.dict(os.environ, {"PICOVOICE_ACCESS_KEY":"teste", "YASM_PORCUPINE_KEYWORD":str(ppn), "YASM_PORCUPINE_MODEL":str(pv)}), patch.dict(
                sys.modules, {"pvporcupine": types.SimpleNamespace(create=Mock(return_value=motor))}
            ):
                detector = PorcupineAtivacao()
                for _ in range(8):
                    detector.alimentar(SOM)
                self.assertEqual(motor.process.call_count, 5)
                self.assertEqual(len(detector.pendente), 0)
                detector.fechar()
                motor.delete.assert_called_once()

    def test_ativacao_nao_usa_google_antes_do_gatilho(self):
        detector, captura = Mock(), Mock()
        detector.alimentar.side_effect = [False, False, True]
        captura.ler.return_value = SOM
        with patch.object(audio, "WAKE_MOTOR", "vosk"), patch.object(audio, "_detector", detector), patch.object(audio, "obter_captura", return_value=captura), patch.object(
            audio.voz, "aguardar_microfone"
        ), patch.object(audio, "gravar_com_sounddevice", return_value=object()) as gravar, patch.object(
            audio, "transcrever_audio", return_value=audio.ResultadoEscuta(1, "Yasmin calcule 2 + 3", "ok")
        ) as transcrever:
            self.assertEqual(audio.aguardar_ativacao(), "yasm calcule 2 + 3")
        transcrever.assert_called_once()
        self.assertEqual(len(gravar.call_args.kwargs["iniciais"]), 3)


class ReconhecimentoTests(unittest.TestCase):
    def test_timeout_faz_um_fallback_do_mesmo_audio(self):
        amostra = object()
        with patch.object(audio, "ASR_FALLBACK", "vosk"), patch.object(audio, "_google", side_effect=TimeoutError), patch.object(audio, "_vosk", return_value="ola") as reserva:
            resultado = audio.transcrever_audio(amostra, motor="google")
        reserva.assert_called_once_with(amostra)
        self.assertTrue(resultado.fallback)
        self.assertEqual(resultado.texto, "ola")

    def test_sucesso_nao_executa_reserva(self):
        with patch.object(audio, "_google", return_value="abra gmail"), patch.object(audio, "_vosk") as reserva:
            resultado = audio.transcrever_audio(object(), motor="google")
        reserva.assert_not_called()
        self.assertFalse(resultado.fallback)

    def test_google_padrao_nao_usa_vosk_automaticamente(self):
        with patch.object(audio, "ASR_FALLBACK", "nenhum"), patch.object(
            audio, "_google", side_effect=audio.sr.RequestError("sem rede")
        ), patch.object(audio, "_vosk") as reserva:
            resultado = audio.transcrever_audio(object(), motor="google")
        reserva.assert_not_called()
        self.assertEqual(resultado.status, "servico_indisponivel")
        self.assertFalse(resultado.fallback)

    def test_ativacao_google_transcreve_frase_uma_vez(self):
        resultados = [audio.ResultadoEscuta(1, "conversa ambiente", "ok", "google"),
                      audio.ResultadoEscuta(2, "Yasmin abra o navegador", "ok", "google")]
        ativar = Mock()
        with patch.object(audio, "WAKE_MOTOR", "google"), patch.object(audio, "_preparado", True), patch.object(
            audio, "gravar_com_sounddevice", return_value=object()
        ) as gravar, patch.object(audio, "transcrever_audio", side_effect=resultados) as transcrever:
            self.assertEqual(audio.aguardar_ativacao(ao_ativar=ativar), "yasm abra o navegador")
        self.assertEqual(gravar.call_count, 2)
        self.assertEqual(transcrever.call_count, 2)
        self.assertTrue(all(chamada.kwargs == {"motor": "google", "usar_reserva": False}
                            for chamada in transcrever.call_args_list))
        ativar.assert_called_once()

    def test_vad_aceita_voz_calibrada_rejeitada_pelo_webrtc(self):
        detector = object.__new__(audio.Vad)
        detector.motor = Mock(is_speech=Mock(return_value=False))
        with patch.object(audio, "_parece_fala", return_value=True), patch.object(audio, "_rms", return_value=500):
            self.assertTrue(detector.fala(SOM, iniciando=True))

    def test_prebuffer_completo_nao_descarta_comando(self):
        captura = Mock()
        captura.ler.side_effect = AssertionError("prebuffer ja completo")
        iniciais = (SILENCIO,) * 5 + (SOM,) * 10 + (SILENCIO,) * 45
        with patch.object(audio, "obter_captura", return_value=captura), patch.object(
            audio, "_vad_atual"
        ) as vad:
            vad.return_value.fala.side_effect = lambda pcm, iniciando: pcm == SOM
            resultado = audio._capturar_segmento(timeout=1, frase_maxima=5, iniciais=iniciais)
        self.assertIn(SOM, resultado)
        captura.ler.assert_not_called()

    def test_mesmo_texto_em_duas_capturas_recebe_ids_distintos(self):
        with patch.object(audio, "_vosk", return_value="aumentar volume"):
            a = audio.transcrever_audio(object(), motor="vosk")
            b = audio.transcrever_audio(object(), motor="vosk")
        self.assertNotEqual(a.id, b.id)
        entrega = EntregaUnica()
        self.assertTrue(entrega.aceitar(a.id))
        self.assertFalse(entrega.aceitar(a.id))
        self.assertTrue(entrega.aceitar(b.id))

    def test_falhas_de_servico_nao_vazam_payload(self):
        with patch.object(audio, "_google", side_effect=RuntimeError("segredo")), patch.object(audio, "_vosk", side_effect=RuntimeError("segredo")), patch("builtins.print") as imprimir:
            resultado = audio.transcrever_audio(object(), motor="google")
        self.assertEqual(resultado.status, "servico_indisponivel")
        self.assertNotIn("segredo", str(imprimir.call_args_list))

    def test_fala_longa_nao_executa_parcial(self):
        with patch.object(audio, "gravar_com_sounddevice", side_effect=audio.FraseLonga), patch.object(audio, "transcrever_audio") as asr:
            self.assertEqual(audio.escutar(), "")
        self.assertEqual(audio.ultimo_resultado.status, "frase_longa")
        asr.assert_not_called()

    def test_silencio_nao_acessa_asr(self):
        with patch.object(audio, "gravar_com_sounddevice", side_effect=audio.sr.WaitTimeoutError), patch.object(audio, "transcrever_audio") as asr:
            self.assertEqual(audio.escutar(), "")
        self.assertEqual(audio.ultimo_resultado.status, "silencio")
        asr.assert_not_called()

    def test_whisper_local_nao_baixa_modelo_implicitamente(self):
        with patch.object(audio, "_whisper", None), patch.dict(os.environ, {"YASM_FASTER_WHISPER_MODEL":""}), patch.dict(sys.modules, {"faster_whisper":Mock()}), self.assertRaises(ValueError):
            audio._carregar_whisper()


class ConversaTests(unittest.TestCase):
    def setUp(self):
        self.estado_anterior = yas.estados
        yas.estados = MaquinaEstados()
        self.addCleanup(setattr, yas, "estados", self.estado_anterior)

    def test_transicao_contraditoria_e_rejeitada(self):
        with self.assertRaises(RuntimeError):
            yas.estados.mudar(Estado.PROCESSANDO_COMANDO)

    def test_fluxo_completo_e_cancelamento(self):
        with patch.object(yas, "configurar_usuario", return_value="Teste"), patch.object(yas, "registrar_historico"), patch.object(yas.voz, "falar", return_value=True), patch.object(yas.audio, "escutar", return_value="cancelar"), patch.object(yas, "processar_comando", return_value="Pronto") as processar:
            yas.conversar("Yasm que horas sao")
        processar.assert_called_once()
        self.assertEqual(yas.estados.estado, Estado.AGUARDANDO_ATIVACAO)

    def test_comando_local_nao_usa_groq(self):
        with patch.object(ia_yasm, "pesquisar") as remoto:
            yas.processar_comando("que horas sao")
        remoto.assert_not_called()
        self.assertEqual(yas.estado_atual()["estado_agente"], "concluido")

    def test_pergunta_aberta_usa_conversa_do_agente(self):
        with patch.object(yas, "inicializar_agente") as agente:
            agente.return_value.atender.return_value = "Resposta"
            self.assertEqual(yas.processar_comando("discuta entropia termodinamica"), "Resposta")
        agente.return_value.atender.assert_called_once()

    def test_intencao_incerta_pede_esclarecimento(self):
        incerta = yas.intent.Intent("ABRIR_APLICATIVO", 0.6)
        with patch.object(yas.intent, "interpretar", return_value=incerta), patch.object(yas.apps, "abrir_aplicativo") as executar:
            self.assertIn("Pode repetir", yas.processar_comando("abra aquele"))
        executar.assert_not_called()

    def test_estado_volta_apos_excecao(self):
        with patch.object(yas, "configurar_usuario", return_value="Teste"), patch.object(yas, "registrar_historico"), patch.object(yas, "processar_comando", side_effect=RuntimeError), self.assertRaises(RuntimeError):
            yas.conversar("Yasm abra gmail")
        self.assertEqual(yas.estados.estado, Estado.AGUARDANDO_ATIVACAO)


class PrivacidadeTests(unittest.TestCase):
    def test_historico_da_sessao_nao_grava_disco_por_padrao(self):
        dados = {"historico": []}
        with patch.object(memoria, "memoria", dados), patch.object(
            memoria, "PERSISTIR_HISTORICO", False
        ), patch.object(memoria, "salvar_memoria") as salvar:
            memoria.registrar_historico("usuario", "teste")
        self.assertEqual(dados["historico"][0]["texto"], "teste")
        salvar.assert_not_called()

    def test_historico_novo_nao_persiste_ao_salvar_tarefa(self):
        with tempfile.TemporaryDirectory() as pasta, patch.object(memoria, "ARQUIVO_MEMORIA", Path(pasta) / "memoria.json"), patch.object(memoria, "PERSISTIR_HISTORICO", False):
            anterior = {"historico":[{"texto":"antigo"}]}
            memoria.salvar_json_atomico(memoria.ARQUIVO_MEMORIA, anterior)
            memoria.salvar_memoria({"historico":[{"texto":"sensivel"}], "tarefas":["teste"]})
            salvo = memoria.carregar_memoria()
            self.assertEqual(salvo["historico"], anterior["historico"])
            self.assertEqual(salvo["tarefas"], ["teste"])

    def test_bloqueio_tts_libera_apos_excecao(self):
        with patch.object(voz, "_falar_serializado", side_effect=RuntimeError), self.assertRaises(RuntimeError):
            voz.falar("teste")
        self.assertFalse(voz._falando.is_set())

    def test_metricas_limitadas_sem_transcricao(self):
        metricas = Metricas(limite=3)
        for n in range(10):
            metricas.medir("asr", n)
        self.assertEqual(metricas.resumo()["tempos_s"]["asr"]["n"], 3)


if __name__ == "__main__":
    unittest.main()
