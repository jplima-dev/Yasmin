"""Treinamento local, persistência e decisões limitadas a planos existentes."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

BASE = Path(__file__).resolve().parents[1] / "Agent"
sys.path.insert(0, str(BASE))

from agente.decisao import DecisorInteracao
from agente.modelo_treinavel import ModeloIntencoesLocal, MotorDecisaoHibrido
from agente.raciocinio import RegrasDeterministicas
from treinar_agente import AVALIACAO, avaliar, exemplos_base, exemplos_usuario


OPERACOES = DecisorInteracao._operacoes_semanticas
ARQUIVO = BASE / "modelos" / "intencoes_local.json"


class ModeloTreinavelTests(unittest.TestCase):
    def test_mil_exemplos_distintos_e_avaliacao_separada(self):
        exemplos = exemplos_base()
        self.assertEqual(len(exemplos), 1000)
        self.assertEqual(len({texto for texto, _ in exemplos}), 1000)
        self.assertFalse({texto for texto, _ in exemplos} & {texto for texto, _ in AVALIACAO})
        modelo = ModeloIntencoesLocal()
        modelo.treinar(exemplos)
        acertos, erros = avaliar(modelo)
        self.assertGreaterEqual(acertos, 26)
        self.assertFalse([erro for erro in erros if erro[1] == "nenhuma" and erro[2] != "nenhuma"])

    def test_arquivo_treinado_persiste_e_pode_ser_retreinado(self):
        modelo = ModeloIntencoesLocal.carregar(ARQUIVO)
        self.assertEqual(modelo.exemplos, 1000)
        with tempfile.TemporaryDirectory() as pasta:
            copia = Path(pasta) / "modelo.json"
            modelo.salvar(copia)
            restaurado = ModeloIntencoesLocal.carregar(copia)
            self.assertEqual(restaurado.prever("quero listar os apps disponíveis"),
                             modelo.prever("quero listar os apps disponíveis"))
            dados = json.loads(copia.read_text(encoding="utf-8"))
            dados["rotulos"] = ["abrir_qualquer_coisa"]
            copia.write_text(json.dumps(dados), encoding="utf-8")
            with self.assertRaises(ValueError):
                ModeloIntencoesLocal.carregar(copia)
            copia.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                ModeloIntencoesLocal.carregar(copia)

    def test_exemplos_do_usuario_entram_no_treinamento(self):
        with tempfile.TemporaryDirectory() as pasta:
            dados = Path(pasta) / "meus_exemplos.jsonl"
            dados.write_text(json.dumps({
                "texto": "Preciso de uma IDE para trabalhar com Kotlin",
                "rotulo": "preparar_programacao",
            }) + "\n", encoding="utf-8")
            extras = exemplos_usuario(dados)
            self.assertEqual(len(extras), 1)
            modelo = ModeloIntencoesLocal()
            modelo.treinar(exemplos_base() + extras)
            self.assertEqual(modelo.exemplos, 1001)

    def test_proposta_local_usa_o_mesmo_decisor_e_apenas_operacao_permitida(self):
        local = ModeloIntencoesLocal.carregar(ARQUIVO)
        externo = Mock()
        motor = MotorDecisaoHibrido(local, externo)
        decisor = DecisorInteracao(RegrasDeterministicas(), motor)
        decisao = decisor.decidir("Estou precisando de uma IDE para trabalhar em Java")
        self.assertEqual(decisao.via, "objetivo")
        self.assertEqual(decisao.origem, "modelo_local")
        self.assertEqual(decisao.objetivo.parametros,
                         {"tipo": "preparar_programacao", "linguagem": "java"})
        externo.classificar.assert_not_called()

    def test_frase_aprendida_percorre_plano_execucao_e_verificacao(self):
        from tests.test_agente import agente_simulado
        agente, _, chamadas = agente_simulado()
        motor = MotorDecisaoHibrido(ModeloIntencoesLocal.carregar(ARQUIVO))
        resposta = agente.atender("Estou precisando de uma IDE para trabalhar em Java",
                                 lambda: Mock(), motor_decisao=motor)
        self.assertIn("Ambiente preparado", resposta)
        self.assertEqual(chamadas, [("localizar", "intellij"), ("abrir", "intellij")])
        self.assertEqual(agente.estado.contexto_imediato["origem_decisao"], "modelo_local")

    def test_pedidos_destrutivos_e_compostos_nao_sao_propostos_pelo_modelo(self):
        modelo = ModeloIntencoesLocal.carregar(ARQUIVO)
        frases = (
            "Apague os arquivos e prepare o ambiente de programação",
            "Não prepare o ambiente para Java",
            "Prepare o ambiente e depois exclua o banco",
            "Como preparar um ambiente para Java?",
            "Quero conversar sobre programação",
        )
        for frase in frases:
            with self.subTest(frase=frase):
                self.assertIsNone(modelo.classificar(frase, [], OPERACOES))

    def test_pedido_de_explicacao_primeiro_nao_executa(self):
        local = ModeloIntencoesLocal.carregar(ARQUIVO)
        externo = Mock()
        motor = MotorDecisaoHibrido(local, externo)
        decisao = DecisorInteracao(RegrasDeterministicas(), motor).decidir(
            "Preciso preparar o ambiente, mas antes me explique o que fará")
        self.assertEqual(decisao.via, "conversa")
        externo.classificar.assert_not_called()
        self.assertIsNone(motor.classificar("Quero conversar sobre código", [], OPERACOES))
        externo.classificar.assert_not_called()

    def test_pedido_misto_destrutivo_nao_chega_a_nenhum_modelo(self):
        local = ModeloIntencoesLocal.carregar(ARQUIVO)
        externo = Mock()
        decisao = DecisorInteracao(RegrasDeterministicas(),
                                   MotorDecisaoHibrido(local, externo)).decidir(
            "Apague meus arquivos e prepare o ambiente de programação")
        self.assertEqual(decisao.via, "esclarecer")
        externo.classificar.assert_not_called()

    def test_modelo_nao_propõe_operacao_fora_da_lista_do_nucleo(self):
        modelo = ModeloIntencoesLocal.carregar(ARQUIVO)
        self.assertIsNone(modelo.classificar("Estou precisando de uma IDE para trabalhar em Java",
                                            [], {}))

    def test_arquivo_corrompido_mantem_fallback_da_yasmin(self):
        import yas
        with (patch.object(yas, "_motor_decisao", None),
              patch.object(ModeloIntencoesLocal, "carregar", side_effect=ValueError("inválido"))):
            motor = yas.inicializar_motor_decisao()
            self.assertIsNone(motor.local)
            self.assertIsNotNone(motor.externo)


if __name__ == "__main__":
    unittest.main()
