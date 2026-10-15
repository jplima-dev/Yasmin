"""Preferências, ensino e contexto usam a memória central sem executar ações."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Agent"))

from agente.conversacao import ServicoConversacao
from agente.decisao import DecisorInteracao
from agente.ferramentas import RegistroFerramentas
from agente.integracao_aplicacoes.raciocinio import RaciocinioAplicacoes
from agente.nucleo import NucleoAgente
from agente.percepcao import Percepcao
from agente.planejamento import Planejador
from agente.raciocinio import RegrasDeterministicas
from agente.verificacao import Verificador


class MemoriaFalsa:
    def __init__(self):
        self.registros = {}
        self.disponivel = True

    def guardar(self, categoria, chave, valor, origem, importancia, confianca):
        if not self.disponivel:
            return False
        self.registros[(categoria, chave)] = {"categoria": categoria, "chave": chave,
                                               "valor": valor, "origem": origem}
        return True

    def recuperar_preferencias(self, limite=12):
        return [item for item in self.registros.values() if item["categoria"] == "preferencia"][:limite]

    def recuperar(self, objetivo, limite=4):
        termos = set(objetivo.descricao.lower().split())
        return [item for item in self.registros.values() if item["categoria"] == "fato"
                and termos.intersection(str(item["valor"]).lower().split())][:limite]

    def esquecer(self, categoria, chave, origem="conversa"):
        return self.registros.pop((categoria, chave), None) is not None


class MotorFalso:
    def __init__(self):
        self.chamadas = []

    def responder(self, mensagens):
        self.chamadas.append(mensagens)
        return "Entendi o assunto."


class ConversacaoTests(unittest.TestCase):
    @staticmethod
    def agente_minimo(memoria=None):
        return NucleoAgente(Percepcao(), memoria or MemoriaFalsa(), RegrasDeterministicas(),
                           Planejador(), RegistroFerramentas(), Verificador())

    def test_preferencia_e_confirmacao_sao_persistidas(self):
        memoria = MemoriaFalsa()
        conversa = ServicoConversacao(memoria)
        self.assertIn("sugiro", conversa.responder("Como você prefere as configurações?"))
        self.assertIn("Guardei", conversa.responder("sim"))
        self.assertEqual(memoria.registros[("preferencia", "tamanho_respostas")]["valor"], "curtas")
        self.assertIn("Guardei", conversa.responder("Prefiro respostas detalhadas"))
        self.assertEqual(memoria.registros[("preferencia", "tamanho_respostas")]["valor"], "detalhadas")

    def test_falha_mysql_nao_declara_aprendizado(self):
        memoria = MemoriaFalsa()
        memoria.disponivel = False
        conversa = ServicoConversacao(memoria)
        self.assertIn("não consegui", conversa.responder("Aprenda que meu editor favorito é VS Code"))
        self.assertEqual(memoria.registros, {})

    def test_ensino_e_recuperacao_seletiva(self):
        memoria = MemoriaFalsa()
        conversa = ServicoConversacao(memoria)
        self.assertIn("Aprendi", conversa.responder("Aprenda que meu editor favorito é VS Code"))
        self.assertIn("VS Code", conversa.responder("Qual meu editor favorito?"))

    def test_correcao_atualiza_fato_e_esquecimento_remove(self):
        memoria = MemoriaFalsa()
        conversa = ServicoConversacao(memoria)
        conversa.responder("Aprenda que meu editor favorito é VS Code")
        self.assertIn("Atualizei", conversa.responder("Corrija que meu editor favorito é IntelliJ"))
        self.assertEqual(len([item for item in memoria.registros.values() if item["categoria"] == "fato"]), 1)
        self.assertIn("IntelliJ", conversa.responder("Qual meu editor favorito?"))
        self.assertIn("Esqueci", conversa.responder("Esqueça meu editor favorito"))
        self.assertFalse(any(item["categoria"] == "fato" for item in memoria.registros.values()))

    def test_curiosidades_nao_repetem_imediatamente(self):
        conversa = ServicoConversacao(MemoriaFalsa())
        primeira = conversa.responder("Me conte uma curiosidade")
        segunda = conversa.responder("Me conte uma curiosidade")
        self.assertNotEqual(primeira, segunda)

    def test_motor_recebe_contexto_limitado_e_preferencias(self):
        memoria = MemoriaFalsa()
        motor = MotorFalso()
        conversa = ServicoConversacao(memoria, motor, limite_contexto=4)
        conversa.responder("Prefiro respostas curtas")
        conversa.responder("Vamos conversar sobre estrelas")
        conversa.responder("E sobre planetas?")
        mensagens = motor.chamadas[-1]
        self.assertEqual(mensagens[0]["role"], "system")
        self.assertIn("curtas", mensagens[0]["content"])
        self.assertIn("estrelas", str(mensagens))
        self.assertLessEqual(len(mensagens), 5)

    def test_motor_recebe_historico_de_comandos_anteriores(self):
        memoria = MemoriaFalsa()
        motor = MotorFalso()
        historico = [{"tipo": "usuario", "texto": "Abra o Workspace"},
                     {"tipo": "yasm", "texto": "Abri o Workspace"},
                     {"tipo": "usuario", "texto": "O que achou dessa tarefa?"}]
        conversa = ServicoConversacao(memoria, motor, historico=lambda: historico)
        conversa.responder("O que achou dessa tarefa?")
        self.assertIn("Abri o Workspace", str(motor.chamadas[-1]))

    def test_relembra_ultima_resposta_sem_inventar_acao(self):
        historico = [{"tipo": "usuario", "texto": "Abra o Workspace"},
                     {"tipo": "yasm", "texto": "Não consegui confirmar a abertura."},
                     {"tipo": "usuario", "texto": "O que fizemos?"}]
        conversa = ServicoConversacao(MemoriaFalsa(), historico=lambda: historico)
        self.assertIn("Não consegui confirmar", conversa.responder("O que fizemos?"))

    def test_frase_complexa_abre_aplicacao_sem_confundir_negacao(self):
        class App:
            id = "workspace-os"
            nome = "Workspace OS"
            pasta = Path("workspace-os")

        class Descoberta:
            aplicacoes = [App()]

        raciocinio = RaciocinioAplicacoes(RegrasDeterministicas(), Path("applications"))
        with patch("agente.integracao_aplicacoes.raciocinio.descobrir_aplicacoes", return_value=Descoberta()):
            objetivo = raciocinio.identificar("Yasmin, você pode abrir o Workspace para eu continuar meu projeto?")
            self.assertEqual(objetivo.parametros["aplicacao"], "workspace-os")
            self.assertIsNone(raciocinio.identificar("Yasmin, não abra o Workspace agora"))
            self.assertIsNone(raciocinio.identificar("Yasmin, não quero abrir o Workspace agora"))
            self.assertIsNone(raciocinio.identificar("Como abrir o Workspace?"))

    def test_rotas_legadas_de_site_e_musica_continuam_disponiveis(self):
        decisor = DecisorInteracao(RegrasDeterministicas())
        self.assertEqual(decisor.decidir("Abra o GitHub", intencao_legada=("SITE", True, {})).via, "legado")
        self.assertEqual(decisor.decidir("Toque música", intencao_legada=("MUSICA", False, {})).via, "legado")

    def test_dispatcher_nao_executa_pedido_negado_ou_multietapa_parcial(self):
        import yas
        agente = self.agente_minimo()
        with patch.object(yas, "inicializar_agente", return_value=agente), patch.object(yas.apps, "abrir_aplicativo") as abrir:
            self.assertIn("Não vou executar", yas.processar_comando("Yasmin, não quero abrir o Workspace agora"))
            self.assertIn("mais de uma ação", yas.processar_comando("Abra o Workspace e depois abra meu projeto"))
        abrir.assert_not_called()

    def test_configuracao_conversada_passa_pelo_dispatcher(self):
        import yas
        memoria = MemoriaFalsa()
        conversa = ServicoConversacao(memoria)

        agente = self.agente_minimo(memoria)
        with patch.object(yas, "_conversacao", conversa), patch.object(yas, "inicializar_agente", return_value=agente), patch.object(yas, "inicializar_conversacao", return_value=conversa):
            self.assertIn("sugiro", yas.processar_comando("Como você prefere as configurações?"))
            self.assertIn("Guardei", yas.processar_comando("sim"))
        self.assertIn(("preferencia", "tom"), memoria.registros)


if __name__ == "__main__":
    unittest.main()
