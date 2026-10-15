"""Regressoes do fluxo completo, com efeitos externos isolados."""
import copy
import errno
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

BASE = Path(__file__).resolve().parents[1] / "Agent"
sys.path.insert(0, str(BASE))
with patch.dict(os.environ, {"YASM_VOICE_SERVER": "1"}):
    import apps_yas as apps
    import comandos_yasm as comandos
    import intent
    import memoria_yasm as memoria
    import yas
    import ia_yasm
    from cerebro.cerebro import CerebroYasm
    from cerebro.contexto import ContextoYasm
    from interface import config_inicial, status

loader = importlib.machinery.SourceFileLoader("launcher_test", str(BASE / "launcher.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
launcher = importlib.util.module_from_spec(spec)
loader.exec_module(launcher)


class ProjetoTests(unittest.TestCase):
    def test_inicializadores_usam_pasta_agent(self):
        raiz = BASE.parent
        bat = (raiz / "iniciar_yasm.bat").read_text(encoding="utf-8")
        vbs = (raiz / "iniciar_yasm.vbs").read_text(encoding="utf-8")
        self.assertTrue((BASE / "launcher.py").is_file())
        self.assertIn('cd /d "%~dp0Agent"', bat)
        self.assertIn('if not exist "%~dp0Agent\\launcher.py"', bat)
        self.assertIn('"iniciar_yasm.bat"', vbs)
        self.assertIn('"Agent"', vbs)
        self.assertIn('Fso.FileExists(LauncherPath)', vbs)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.caminho = Path(self.temp.name) / "memoria.json"
        original = copy.deepcopy(memoria.memoria)
        self.addCleanup(lambda: (memoria.memoria.clear(), memoria.memoria.update(original)))
        memoria.memoria.clear()
        memoria.memoria.update(memoria.garantir_memoria_base({"usuario": {"nome": "Teste"}}))
        for alvo, atributo, valor in (
            (memoria, "ARQUIVO_MEMORIA", self.caminho),
            (apps, "aplicativos_instalados", Mock(return_value={})),
            (comandos, "informar", Mock()),
            (comandos.webbrowser, "open", Mock()),
            (yas.voz, "falar", Mock(return_value=True)),
            (yas.audio, "diagnostico_audio", Mock(return_value="microfone simulado")),
            (yas.cerebro, "lembrar_usuario", Mock()),
            (ia_yasm, "disponivel", Mock(return_value=False)),
            (yas.audio, "ultimo_resultado", yas.audio.ResultadoEscuta()),
        ):
            alteracao = patch.object(alvo, atributo, valor)
            alteracao.start()
            self.addCleanup(alteracao.stop)
        if comandos.requests is not None:
            alteracao = patch.object(comandos.requests, "get", side_effect=AssertionError("rede inesperada"))
            alteracao.start()
            self.addCleanup(alteracao.stop)

    def test_intencoes_locais_nao_viram_pesquisa(self):
        casos = {
            "Yasmin, calcule 2 + 3": "CALCULO", "quanto é 2,5 * 4?": "CALCULO",
            "quem é você": "IDENTIDADE", "qual é a data": "DATA",
            "que horas são": "HORA", "ajuda": "AJUDA", "status": "STATUS",
            "concluir tarefa lavar louça": "TAREFAS", "minhas notas": "MEMORIA",
            "me explique listas em Python": "ESTUDO", "clima em Recife": "CLIMA",
            "abra o gmail": "SITE", "abra o segundo resultado": "RESULTADO_PESQUISA",
        }
        for texto, nome in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(intent.interpretar(texto, fallback_pesquisa=False).nome, nome)

    def test_pesquisa_explicita_continua_pesquisa(self):
        self.assertEqual(intent.interpretar("pesquise clima em Recife").nome, "PESQUISA")

    def test_calculos_preservam_operadores_no_dispatcher(self):
        with patch.object(comandos.falas, "escolher", side_effect=lambda chave, **kw: (chave, kw)):
            for texto, resultado in (("Yasmin, calcule 2 + 3", 5), ("quanto é 2,5 * 4?", 10),
                                     ("calcule 10 - 3", 7), ("calcule -2 ** 3", -8)):
                with self.subTest(texto=texto):
                    resposta = yas.processar_comando(texto)
                    self.assertEqual(resposta, ("calculo_resultado", {"resultado": resultado}))

    def test_calculadora_rejeita_execucao_e_resultados_excessivos(self):
        for expressao in ("__import__('os')", "9 ** 999999999", "True", "1e999"):
            with self.subTest(expressao=expressao), self.assertRaises(ValueError):
                comandos.calcular_expressao_segura(expressao)

    def test_tarefa_desconhecida_nao_conclui_primeira(self):
        memoria.memoria["tarefas"] = [{"texto": "estudar", "concluida": False}]
        resposta = yas.processar_comando("concluir tarefa lavar louça")
        self.assertIn("Nao encontrei", resposta)
        self.assertFalse(memoria.memoria["tarefas"][0]["concluida"])

    def test_comandos_memoria_e_tarefas_persistem(self):
        yas.processar_comando("nova tarefa estudar python")
        yas.processar_comando("lembre que gosto de livros")
        dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        self.assertEqual(dados["tarefas"][0]["texto"], "estudar python")
        self.assertEqual(dados["notas"][0]["texto"], "gosto de livros")

    def test_pergunta_inicial_nao_e_descartada(self):
        with patch.object(yas.audio, "escutar", return_value=""), patch.object(
            yas, "processar_comando", return_value="Sao dez horas."
        ) as processar:
            yas.conversar("Yasmin, que horas são?")
        processar.assert_called_once_with("Yasmin, que horas são?")
        yas.voz.falar.assert_called_once_with("Sao dez horas.")

    def test_pergunta_local_nao_acessa_rede(self):
        with patch.object(yas, "_pesquisar_fallback", side_effect=AssertionError("pesquisa inesperada")):
            for texto in ("quem é você", "qual é a data", "que horas são", "ajuda", "status"):
                with self.subTest(texto=texto):
                    self.assertTrue(yas.processar_comando(texto))

    def test_frase_desconhecida_nao_pesquisa(self):
        with patch.object(yas, "_pesquisar_fallback", side_effect=AssertionError("pesquisa inesperada")):
            self.assertTrue(yas.processar_comando("o céu tem uma cor bonita"))

    def test_resposta_de_quiz_chega_ao_executor(self):
        memoria.memoria["estudo"]["quiz_atual"] = 0
        with patch.object(intent, "interpretar", return_value=intent.Intent(
            nome="DESCONHECIDA", confianca=0, texto_corrigido="resposta"
        )), patch.object(comandos, "responder_quiz_python", return_value="Acertou!") as responder:
            self.assertEqual(yas.processar_comando("resposta"), "Acertou!")
        responder.assert_called_once_with("resposta")

    def test_quiz_invalido_nao_quebra_comando(self):
        memoria.memoria["estudo"]["quiz_atual"] = 9999
        self.assertIsNone(comandos.responder_quiz_python("algo"))

    def test_json_anterior_sobrevive_falha_serializacao(self):
        self.assertTrue(memoria.salvar_json_atomico(self.caminho, {"nome": "Joao"}))
        self.assertFalse(memoria.salvar_json_atomico(self.caminho, {"invalido": object()}))
        self.assertEqual(json.loads(self.caminho.read_text()), {"nome": "Joao"})
        self.assertEqual(list(self.caminho.parent.glob("*.tmp")), [])

    def test_json_anterior_sobrevive_falha_substituicao(self):
        self.caminho.write_text('{"preservado": true}', encoding="utf-8")
        with patch.object(memoria.os, "replace", side_effect=OSError("ocupado")):
            self.assertFalse(memoria.salvar_json_atomico(self.caminho, {"novo": True}))
        self.assertEqual(json.loads(self.caminho.read_text()), {"preservado": True})
        self.assertEqual(list(self.caminho.parent.glob("*.tmp")), [])

    def test_cerebro_contexto_e_persistencia(self):
        cerebro = CerebroYasm(self.caminho, chance_pergunta=0)
        cerebro.lembrar_usuario("nome", "Teste")
        resposta = cerebro.processar("oi", "Uma resposta longa para verificar iniciativa.", assunto="estudo")
        self.assertFalse(resposta["perguntar"])
        self.assertEqual(cerebro.estado()["ultima_fala_usuario"], "oi")
        self.assertEqual(CerebroYasm(self.caminho).memoria["usuario"]["nome"], "Teste")
        cerebro.limpar_contexto()
        self.assertEqual(cerebro.estado()["historico"], [])

    def test_historico_exportado_nao_altera_original(self):
        contexto = ContextoYasm()
        contexto.adicionar_usuario("oi")
        contexto.obter_historico()[0]["texto"] = "alterado"
        self.assertEqual(contexto.ultima_fala_usuario(), "oi")

    def test_opcoes_naturais_nao_confundem_numeros_e_substrings(self):
        casos = (
            ("um pouco de tudo", {"1": "programacao", "6": "um pouco de tudo"}, "6"),
            ("informal", {"1": "seria", "2": "descontraida"}, "2"),
            ("sim", {"1": "sim pesquise automaticamente", "2": "pergunte antes", "3": "nao pesquise"}, "1"),
            ("não", {"1": "sim pesquise automaticamente", "2": "pergunte antes", "3": "nao pesquise"}, "3"),
            ("opção dois", {"1": "seria", "2": "descontraida"}, "2"),
            ("as vezes", {"1": "sim", "2": "as vezes", "3": "nao"}, "2"),
        )
        for texto, opcoes, esperado in casos:
            with self.subTest(texto=texto):
                self.assertEqual(config_inicial.interpretar_opcao(texto, opcoes), esperado)

    def test_executavel_procura_candidatos_posteriores(self):
        with patch.object(apps.shutil, "which", side_effect=lambda nome: "C:/apps/segundo.exe" if nome == "segundo.exe" else None):
            self.assertEqual(apps._encontrar_executavel(["primeiro.exe", "segundo.exe"]), "C:/apps/segundo.exe")

    def test_alias_curto_nao_identifica_outro_app(self):
        self.assertIsNone(apps.identificar_aplicativo("abre calculando"))
        self.assertEqual(apps.identificar_aplicativo("abre a calculadora"), "calculadora")

    def test_fechar_nao_abre_aplicativo(self):
        with patch.object(apps, "abrir_aplicativo") as abrir:
            self.assertIsNone(apps.comando_abrir_aplicativo("fecha chrome"))
        abrir.assert_not_called()

    def test_falha_taskkill_nao_propaga(self):
        with patch.object(apps.subprocess, "run", side_effect=OSError("indisponivel")):
            self.assertIn("nao esta aberto", apps.fechar_aplicativo("opera"))

    def test_atalho_informa_falhas_reais(self):
        with patch.object(apps, "abrir_aplicativo", return_value="Nao encontrei aplicativo."):
            self.assertIn("Nao encontrei", apps.comando_atalho("bd"))

    def test_launcher_aceita_yasm_sem_substrings(self):
        self.assertTrue(launcher.deve_iniciar("Yasm"))
        self.assertTrue(launcher.deve_iniciar("Yasmin, que horas são?"))
        self.assertFalse(launcher.deve_iniciar("yasuo"))
        self.assertEqual(launcher.comando_inicial("iniciar yasm"), "yasm")

    def test_estado_visual_reflete_fala_e_etapa_real(self):
        from agente.modelos import StatusAgente

        agente = Mock()
        agente.estado.status = StatusAgente.EXECUTANDO
        agente.estado.tarefa_atual = "Exportar contexto do projeto"
        agente.estado.processos = [{"descricao": "Exportar contexto do projeto", "status": "executando"}]
        with patch.object(yas, "_agente", agente), patch.object(yas.voz, "falando", return_value=True):
            estado = yas.estado_atual()
        self.assertEqual(estado["estado_agente"], "executando")
        self.assertEqual(estado["tarefa_atual"], "Exportar contexto do projeto")
        self.assertIs(estado["falando"], True)
        self.assertEqual(estado["processos"], agente.estado.processos)

    def test_resposta_do_workspace_dispara_voz_sem_bloquear_texto(self):
        recebida, concluiu = [], threading.Event()

        def sintetizar(texto):
            recebida.append(texto)
            concluiu.set()

        with patch.dict(os.environ, {"YASM_VOZ_WORKSPACE": "1"}):
            launcher.falar_resposta_workspace("Tarefa concluída", sintetizar)
        self.assertTrue(concluiu.wait(1))
        self.assertEqual(recebida, ["Tarefa concluída"])
        with patch.dict(os.environ, {"YASM_VOZ_WORKSPACE": "0"}):
            launcher.falar_resposta_workspace("Silêncio", sintetizar)
        self.assertEqual(recebida, ["Tarefa concluída"])

    def test_launcher_reconhece_instancia_ativa_pelo_canal_real(self):
        from servicos.comandos_workspace import criar_servidor_comandos

        servidor = criar_servidor_comandos(
            lambda texto: texto, porta=0,
            estado=lambda: {"estado_agente": "concluido",
                            "estado_voz": "aguardando_ativacao"},
        )
        thread = threading.Thread(target=servidor.serve_forever, daemon=True)
        thread.start()
        try:
            self.assertTrue(launcher.instancia_yasmin_ativa(servidor.server_port))
        finally:
            servidor.shutdown()
            servidor.server_close()
            thread.join(timeout=2)

    def test_launcher_reabre_workspace_quando_ja_esta_ativo(self):
        ocupada = OSError(errno.EADDRINUSE, "porta ocupada")
        with patch.object(launcher, "iniciar_servidor_status", side_effect=ocupada), \
             patch.object(launcher, "instancia_yasmin_ativa", return_value=True), \
             patch("interface.janela_workspace.abrir_janela", return_value=True) as janela, \
             patch.object(launcher.audio, "encerrar"), \
             patch.object(launcher.status, "fechar"):
            self.assertEqual(launcher.main(), 0)
        janela.assert_called_once_with()

    def test_launcher_nao_confunde_outra_aplicacao_com_yasmin(self):
        ocupada = OSError(errno.EADDRINUSE, "porta ocupada")
        with patch.object(launcher, "iniciar_servidor_status", side_effect=ocupada), \
             patch.object(launcher, "instancia_yasmin_ativa", return_value=False), \
             patch("interface.janela_workspace.abrir_janela") as janela, \
             patch.object(launcher.audio, "encerrar"), \
             patch.object(launcher.status, "fechar"):
            self.assertEqual(launcher.main(), 1)
        janela.assert_not_called()

    def test_launcher_mantem_janela_apos_falha_de_microfone(self):
        processo = Mock()
        processo.poll.return_value = None
        with patch.object(launcher, "iniciar_servidor_status"), patch.object(
            launcher, "iniciar_interface_workspace"
        ), patch.object(
            launcher, "calibrar"
        ), patch.object(launcher, "RECONHECIMENTO_ONLINE", True), patch.object(
            launcher, "aguardar_servico_voz", return_value=False
        ), patch.object(launcher.subprocess, "Popen", return_value=processo), patch.object(
            launcher.status, "iniciar"
        ), patch.object(launcher.status, "desligada"), patch.object(
            launcher.status, "fechar"
        ), patch.object(launcher.threading, "Thread"), patch.object(
            launcher, "escutar", side_effect=[RuntimeError("microfone falhou"), KeyboardInterrupt()]
        ), patch.object(launcher.time, "sleep"):
            self.assertEqual(launcher.main(), 0)
        processo.terminate.assert_called_once()

    def test_hud_atualiza_sem_chamar_tk_em_outra_thread(self):
        hud = status.StatusYasm()
        hud._root = Mock()
        hud._label = Mock()
        hud.desligada()
        hud.fechar()
        hud._root.after.assert_not_called()
        self.assertTrue(hud._fechando.is_set())


if __name__ == "__main__":
    unittest.main()
