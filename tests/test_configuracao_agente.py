"""Fluxo de configuração do Agent Core sem serviços externos."""

import os
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

BASE = Path(__file__).resolve().parents[1] / "Agent"
sys.path.insert(0, str(BASE))

from agente.configuracao import SessaoConfiguracao
from agente.modelos import EstadoAgente


class ConfiguracaoAgenteTests(unittest.TestCase):
    def test_perguntas_e_interpretacao_ficam_no_core(self):
        agente = SimpleNamespace(estado=EstadoAgente(), memoria=Mock())
        agente.conversar = Mock(return_value="Posso ajudar com isso durante a configuração.")
        conversa = Mock()
        sessao = SessaoConfiguracao(agente, conversa, semente=1)
        self.assertIn("nome_usuario", sessao.topico_atual)
        primeira = sessao.formular()
        self.assertTrue(primeira)
        self.assertEqual(agente.estado.contexto_imediato["configuracao_topico"], "nome_usuario")
        self.assertFalse(sessao.receber("Por que você precisa disso?").aceita)
        self.assertEqual(sessao.topico_atual, "nome_usuario")
        nome = sessao.receber("pode me chamar de Ruan")
        self.assertTrue(nome.aceita)
        self.assertIn("Ruan", nome.mensagem)
        self.assertEqual(sessao.respostas["nome_usuario"], "Ruan")
        sessao.formular()
        self.assertFalse(sessao.receber("você sabe me ajudar com Python?").aceita)
        self.assertEqual(sessao.topico_atual, "nome_assistente")
        agente.conversar.assert_called_once()
        assistente = sessao.receber("vou te chamar de Yasmin")
        self.assertTrue(assistente.aceita)
        self.assertIn("Yasmin", assistente.mensagem)

        respostas = (
            "quero algo leve", "respostas curtas e objetivas",
            "pergunte antes de pesquisar", "sim, pode tentar corrigir",
            "sugira quando fizer sentido", "não, prefiro ouvir até o fim",
            "não quero memória", "só quando eu precisar",
            "sim, cumprimente", "quero depurar código e revisar bugs",
            "já programo, mas ainda tenho alguma experiência",
        )
        for resposta in respostas:
            sessao.formular()
            self.assertTrue(sessao.receber(resposta).aceita, (sessao.topico_atual, resposta))
        self.assertTrue(sessao.concluida)
        self.assertEqual(sessao.respostas["tipo_memoria"], None)
        configuracao = sessao.configuracao()
        preferencias = configuracao["preferencias"]
        self.assertEqual(preferencias["pesquisa_automatica"], "perguntar")
        self.assertEqual(preferencias["uso_principal"], "revisao e depuracao")
        self.assertFalse(preferencias["memoria_ativa"])
        self.assertEqual(sessao.sincronizar_preferencias(preferencias), 0)
        agente.memoria.guardar.assert_not_called()

    def test_variantes_cancelamento_e_teste_de_voz(self):
        a = SessaoConfiguracao(semente=0)
        b = SessaoConfiguracao(semente=1)
        self.assertNotEqual(a.formular(), b.formular())
        self.assertTrue(a.receber("cancelar configuração").cancelada)
        self.assertFalse(a.concluida)
        sessao = SessaoConfiguracao(vozes={"1": {"id": "voz:um", "nome": "Voz Um"}},
                                    semente=0)
        respostas = ["Ruan", "Yasmin", "equilibrada", "diretas", "pergunte antes",
                     "sim", "às vezes", "sim", "não", "não", "sim",
                     "automatizar tarefas", "avançado"]
        for resposta in respostas:
            sessao.formular()
            self.assertTrue(sessao.receber(resposta).aceita)
        self.assertEqual(sessao.topico_atual, "voz")
        self.assertEqual(sessao.receber("teste a voz 1").acao, "testar_voz")
        self.assertEqual(sessao.topico_atual, "voz")
        self.assertTrue(sessao.receber("primeira").concluida)
        self.assertEqual(sessao.configuracao()["voz"]["id"], "voz:um")

    def test_confirmacao_de_conversa_nao_vira_resposta_da_pergunta(self):
        conversa = Mock()
        conversa.confirmacao_pendente = True
        agente = SimpleNamespace(estado=EstadoAgente(), memoria=Mock(),
                                 conversar=Mock(return_value="Registrei essa escolha."))
        sessao = SessaoConfiguracao(agente, conversa)
        sessao.formular()
        retorno = sessao.receber("sim")
        self.assertFalse(retorno.aceita)
        self.assertEqual(retorno.mensagem, "Registrei essa escolha.")
        self.assertEqual(sessao.topico_atual, "nome_usuario")

    def test_pesquisa_pede_antes_mesmo_com_frase_negativa(self):
        sessao = SessaoConfiguracao()
        for resposta in ("Ruan", "Yasmin", "equilibrada", "diretas"):
            sessao.formular()
            self.assertTrue(sessao.receber(resposta).aceita)
        self.assertEqual(sessao.topico_atual, "pesquisa_automatica")
        self.assertTrue(sessao.receber("não pesquise sem me perguntar antes").aceita)
        self.assertEqual(sessao.respostas["pesquisa_automatica"], "perguntar")

    def test_interface_apenas_conduz_voz_e_persiste_schema_legado(self):
        with patch.dict(os.environ, {"YASM_VOICE_SERVER": "1"}):
            from interface import config_inicial as tela
        respostas = ["Meu nome é Ruan", "Yasmin", "equilibrada", "diretas",
                     "pergunte antes", "sim", "às vezes", "sim", "não",
                     "não", "sim", "organizar projetos", "intermediário"]
        dados = {}
        with (patch.object(tela, "memoria", dados),
              patch.object(tela, "OPCOES_VOZ", {}),
              patch.object(tela, "falar") as fala,
              patch.object(tela, "ouvir", side_effect=respostas),
              patch.object(tela, "salvar_memoria", return_value=True) as salvar,
              patch.object(tela.voz, "obter_voz_atual", return_value="voz:padrao"),
              patch.object(tela.voz, "definir_voz")):
            self.assertTrue(tela.iniciar())
        self.assertTrue(dados["configuracao"]["concluida"])
        self.assertEqual(dados["usuario"]["nome"], "Ruan")
        self.assertEqual(dados["preferencias"]["uso_principal"], "projetos e workspace")
        self.assertEqual(dados["voz"]["id"], "voz:padrao")
        salvar.assert_called_once()
        self.assertTrue(fala.called)

    def test_falha_ao_salvar_nao_marca_configuracao_completa(self):
        with patch.dict(os.environ, {"YASM_VOICE_SERVER": "1"}):
            from interface import config_inicial as tela
        respostas = ["Ruan", "Yasmin", "equilibrada", "diretas", "pergunte antes",
                     "sim", "às vezes", "sim", "não", "não", "sim", "revisar código", "avançado"]
        dados = {"historico": [{"texto": "preservar"}]}
        with (patch.object(tela, "memoria", dados), patch.object(tela, "OPCOES_VOZ", {}),
              patch.object(tela, "falar"), patch.object(tela, "ouvir", side_effect=respostas),
              patch.object(tela, "salvar_memoria", return_value=False),
              patch.object(tela.voz, "obter_voz_atual", return_value="voz:padrao")):
            self.assertFalse(tela.iniciar())
        self.assertEqual(dados, {"historico": [{"texto": "preservar"}]})


if __name__ == "__main__":
    unittest.main()
