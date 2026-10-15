"""Ciclo completo do agente com capacidades e memória isoladas."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Agent"))

from agente.ferramentas import Ferramenta, RegistroFerramentas
from agente.modelos import (Objetivo, ResultadoFerramenta, ResultadoVerificacao,
                            Risco, StatusAgente, StatusEtapa, StatusVerificacao)
from agente.nucleo import NucleoAgente
from agente.percepcao import Percepcao
from agente.planejamento import Planejador
from agente.raciocinio import RegrasDeterministicas
from agente.verificacao import Verificador


class MemoriaFalsa:
    def __init__(self):
        self.consultas = []
        self.experiencias = []
        self.objetivos = []

    def recuperar(self, objetivo, limite=8):
        self.consultas.append((objetivo, limite))
        return []

    def registrar_experiencia(self, objetivo, aplicativo):
        self.experiencias.append((objetivo, aplicativo))

    def registrar_objetivo(self, objetivo, status):
        self.objetivos.append((objetivo, status))


def agente_simulado(falhar_vscode=False, processo_incerto=False):
    memoria = MemoriaFalsa()
    chamadas = []
    registro = RegistroFerramentas()

    def localizar(nome):
        chamadas.append(("localizar", nome))
        return ResultadoFerramenta(False, erro="ausente") if nome == "vscode" and falhar_vscode else ResultadoFerramenta(True, {"caminho": nome})

    def abrir(nome):
        chamadas.append(("abrir", nome))
        return ResultadoFerramenta(True, {"nome": nome})

    registro.registrar(Ferramenta("localizar_aplicativo", "Localizar", ("nome",), Risco.BAIXO, localizar, "executavel"))
    registro.registrar(Ferramenta("abrir_aplicativo", "Abrir", ("nome",), Risco.MEDIO, abrir, "processo"))
    verificador = Verificador()
    verificador.registrar("executavel", lambda etapa, obs: ResultadoVerificacao(
        StatusVerificacao.SUCESSO if obs.dados["sucesso"] else StatusVerificacao.FALHA,
        1.0, ("executável",)))
    verificador.registrar("processo", lambda etapa, obs: ResultadoVerificacao(
        StatusVerificacao.INCERTO if processo_incerto else StatusVerificacao.SUCESSO,
        0.4 if processo_incerto else 1.0, ("processo observado" if not processo_incerto else "sem processo",)))
    return NucleoAgente(Percepcao(), memoria, RegrasDeterministicas(), Planejador(), registro, verificador), memoria, chamadas


class AgenteTests(unittest.TestCase):
    def test_objetivo_completo_coordena_seis_pilares(self):
        agente, memoria, chamadas = agente_simulado()
        resultado = agente.executar("Prepare meu ambiente de programação.")
        self.assertEqual(resultado.status, StatusAgente.CONCLUIDO)
        self.assertEqual(chamadas, [("localizar", "vscode"), ("abrir", "vscode")])
        self.assertEqual(len(memoria.consultas), 1)
        self.assertEqual(len(memoria.experiencias), 1)
        self.assertEqual(memoria.objetivos[0][1], "concluido")
        self.assertEqual([e.status for e in resultado.estado.plano_atual.etapas],
                         [StatusEtapa.CONCLUIDA, StatusEtapa.CONCLUIDA])
        self.assertEqual(resultado.estado.ultima_observacao.tipo, "resultado_ferramenta")
        self.assertEqual(resultado.estado.plano_atual.revisao, 0)

    def test_frase_complexa_local_prepara_ambiente(self):
        agente, _, chamadas = agente_simulado()
        self.assertIn("Ambiente preparado", agente.atender(
            "Me ajude a deixar tudo pronto para codar Java", lambda: Mock()))
        self.assertEqual(chamadas, [("localizar", "intellij"), ("abrir", "intellij")])

    def test_falha_replaneja_e_verifica_alternativa(self):
        agente, memoria, chamadas = agente_simulado(falhar_vscode=True)
        resultado = agente.executar("Prepare meu ambiente de programação.")
        self.assertEqual(resultado.status, StatusAgente.CONCLUIDO)
        self.assertEqual(chamadas, [("localizar", "vscode"), ("localizar", "intellij"), ("abrir", "intellij")])
        self.assertEqual(resultado.estado.plano_atual.revisao, 1)
        self.assertEqual(memoria.experiencias[0][1], "intellij")

    def test_incerteza_bloqueia_conclusao_e_aprendizado(self):
        agente, memoria, chamadas = agente_simulado(processo_incerto=True)
        resultado = agente.executar("Prepare meu ambiente de programação.")
        self.assertEqual(resultado.status, StatusAgente.BLOQUEADO)
        self.assertEqual(resultado.estado.etapa_atual.status, StatusEtapa.INCERTA)
        self.assertEqual(memoria.experiencias, [])

    def test_comando_e_objetivo_sao_planos_distintos(self):
        agente, _, chamadas = agente_simulado()
        comando = Objetivo("Abra o VS Code", tipo="comando", parametros={"aplicativo": "vscode"})
        resultado = agente.executar(comando.descricao, comando)
        self.assertEqual(resultado.status, StatusAgente.CONCLUIDO)
        self.assertEqual(chamadas, [("abrir", "vscode")])
        self.assertEqual(len(resultado.estado.plano_atual.etapas), 1)

    def test_risco_alto_requer_confirmacao(self):
        agente, _, _ = agente_simulado()
        agente.executor.registro.registrar(Ferramenta("perigosa", "Alto risco", (), Risco.ALTO,
                                                     lambda: ResultadoFerramenta(True, {})))
        self.assertFalse(agente.executor.executar("perigosa", {}).sucesso)
        self.assertTrue(agente.executor.executar("perigosa", {}, confirmado=True).sucesso)

    def test_fechamento_forcado_so_ocorre_apos_confirmacao_e_verificacao(self):
        agente, _, chamadas = agente_simulado()
        agente.executor.registro.registrar(Ferramenta(
            "fechar_aplicativo", "Fecha aplicativo", ("nome",), Risco.ALTO,
            lambda nome: (chamadas.append(("fechar", nome)) or ResultadoFerramenta(True, {"nome": nome})),
            "processo_encerrado"))
        agente.verificador.registrar("processo_encerrado", lambda etapa, obs: ResultadoVerificacao(
            StatusVerificacao.SUCESSO, 1.0, ("processo ausente",)))
        conversa = Mock()
        primeira = agente.atender("Feche o VS Code", lambda: conversa,
                                 intencao_legada=("FECHAR_APLICATIVO", True, {"aplicativo": "vscode"}))
        self.assertIn("Confirmação necessária", primeira)
        self.assertEqual(chamadas, [])
        self.assertEqual(agente.atender("Yasmin, sim", lambda: conversa), "Fechei vscode.")
        self.assertEqual(chamadas, [("fechar", "vscode")])
        self.assertEqual(agente.estado.etapa_atual.evidencia.status, StatusVerificacao.SUCESSO)

    def test_confirmacao_negada_cancela_fechamento(self):
        agente, _, chamadas = agente_simulado()
        agente.executor.registro.registrar(Ferramenta(
            "fechar_aplicativo", "Fecha aplicativo", ("nome",), Risco.ALTO,
            lambda nome: (chamadas.append(("fechar", nome)) or ResultadoFerramenta(True, {})),
            "processo_encerrado"))
        agente.atender("Feche o VS Code", lambda: Mock(),
                      intencao_legada=("FECHAR_APLICATIVO", True, {"aplicativo": "vscode"}))
        self.assertIn("Cancelei", agente.atender("não", lambda: Mock()))
        self.assertEqual(chamadas, [])

    def test_modelo_semantico_so_pode_escolher_plano_validado(self):
        agente, _, chamadas = agente_simulado()
        motor = Mock()
        motor.classificar.return_value = {"operacao": "preparar_programacao", "linguagem": "java"}
        resultado = agente.atender("Me ajude a deixar tudo pronto pra codar Java", lambda: Mock(),
                                  motor_decisao=motor)
        self.assertIn("Ambiente preparado", resultado)
        self.assertEqual(chamadas, [("localizar", "intellij"), ("abrir", "intellij")])
        self.assertEqual(agente.estado.contexto_imediato.get("memorias_recuperadas"), 0)
        agente2, _, chamadas2 = agente_simulado()
        motor.classificar.return_value = {"operacao": "apagar_arquivos", "caminho": "C:/"}
        self.assertIn("Qual resultado concreto", agente2.atender(
            "Me ajude a apagar tudo", lambda: Mock(), motor_decisao=motor))
        self.assertEqual(chamadas2, [])

    def test_saudacao_nao_planeja_nem_chama_classificador(self):
        agente, memoria, chamadas = agente_simulado()
        conversa = Mock(responder=Mock(return_value="Oi!"))
        motor = Mock()
        self.assertEqual(agente.atender("Oi", lambda: conversa, motor_decisao=motor), "Oi!")
        self.assertEqual(chamadas, [])
        self.assertEqual(memoria.consultas, [])
        motor.classificar.assert_not_called()

    def test_site_legado_conclui_estado_sem_chamar_modelo(self):
        agente, _, chamadas = agente_simulado()
        motor = Mock()
        self.assertIsNone(agente.atender("abra o GitHub", lambda: Mock(),
                                        intencao_legada=("SITE", True, {}), motor_decisao=motor))
        agente.concluir_legado("Abrindo GitHub")
        self.assertEqual(agente.estado.status, StatusAgente.CONCLUIDO)
        self.assertEqual(chamadas, [])
        motor.classificar.assert_not_called()

    def test_novo_comando_legado_nao_exibe_etapas_da_tarefa_anterior(self):
        agente, _, _ = agente_simulado()
        agente.executar("Prepare meu ambiente de programação.")
        self.assertTrue(any("Objetivo" in item["descricao"] for item in agente.estado.processos))
        self.assertIsNone(agente.atender("abra o GitHub", lambda: Mock(),
                                        intencao_legada=("SITE", True, {})))
        agente.concluir_legado("Abrindo GitHub")
        self.assertEqual([item["descricao"] for item in agente.estado.processos],
                         ["Interpretando pedido", "Comando concluído"])

    def test_musica_explicita_preserva_rota_legada(self):
        agente, _, chamadas = agente_simulado()
        self.assertIsNone(agente.atender("toque uma música", lambda: Mock(),
                                        intencao_legada=("MUSICA", False, {})))
        self.assertEqual(chamadas, [])

    def test_sem_verificador_nao_gera_sucesso_falso(self):
        verificador = Verificador()
        from agente.modelos import Etapa, Observacao
        self.assertEqual(verificador.verificar(Etapa("x", "x"), Observacao("x", "x", {})).status,
                         StatusVerificacao.INCERTO)

    def test_ferramenta_ausente_retorna_falha_sem_excecao(self):
        agente, _, _ = agente_simulado()
        del agente.executor.registro._ferramentas["localizar_aplicativo"]
        self.assertFalse(agente.executor.executar("localizar_aplicativo", {}).sucesso)
        resultado = agente.executar("Prepare meu ambiente de programação.")
        self.assertEqual(resultado.status, StatusAgente.FALHOU)
        self.assertEqual(resultado.estado.etapa_atual.status, StatusEtapa.FALHOU)

    def test_erro_do_verificador_retorna_incerteza(self):
        agente, _, _ = agente_simulado()
        agente.verificador.registrar("executavel", Mock(side_effect=RuntimeError("falhou")))
        with patch("agente.nucleo.log.debug"):
            resultado = agente.executar("Prepare meu ambiente de programação.")
        self.assertEqual(resultado.status, StatusAgente.BLOQUEADO)
        self.assertEqual(resultado.estado.etapa_atual.status, StatusEtapa.INCERTA)

    def test_resultado_invalido_do_verificador_retorna_incerteza(self):
        agente, _, _ = agente_simulado()
        agente.verificador.registrar("executavel", Mock(return_value=None))
        with patch("agente.nucleo.log.debug"):
            resultado = agente.executar("Prepare meu ambiente de programação.")
        self.assertEqual(resultado.status, StatusAgente.BLOQUEADO)
        self.assertEqual(resultado.estado.etapa_atual.status, StatusEtapa.INCERTA)

    def test_entrada_principal_encaminha_objetivo_ao_agente(self):
        import yas
        memoria = Mock()
        agente = Mock(memoria=memoria)
        agente.atender.return_value = "Ambiente preparado: vscode."
        with patch.object(yas, "inicializar_agente", return_value=agente):
            self.assertEqual(yas.processar_comando("Prepare meu ambiente de programação."),
                             "Ambiente preparado: vscode.")
        agente.atender.assert_called_once()
        memoria.migrar_memorias_existentes.assert_not_called()

    def test_verificacao_de_aplicativo_usa_processo_observado(self):
        from agente import adaptadores_yasm as adaptadores
        from agente.modelos import Etapa, Observacao
        etapa = Etapa("Abrir vscode", "abrir_aplicativo", {"nome": "vscode"}, verificacao="processo")
        observacao = Observacao("resultado_ferramenta", "abrir_aplicativo", {"sucesso": True, "resultado": {}})
        with patch.object(adaptadores, "processos_ativos", return_value={"code.exe"}):
            self.assertEqual(adaptadores.verificar_processo(etapa, observacao).status,
                             StatusVerificacao.SUCESSO)
        with patch.object(adaptadores, "processos_ativos", return_value=None):
            self.assertEqual(adaptadores.verificar_processo(etapa, observacao).status,
                             StatusVerificacao.INCERTO)

    def test_consulta_de_processos_usa_alternativa_quando_tasklist_falha(self):
        import subprocess
        from agente import adaptadores_yasm as adaptadores
        saida = Mock(stdout="Code\nexplorer\n")
        with patch.object(adaptadores.subprocess, "run", side_effect=[
            subprocess.CalledProcessError(1, "tasklist"), saida
        ]) as executar:
            processos = adaptadores.processos_ativos()
        self.assertIn("code.exe", processos)
        self.assertIn("explorer.exe", processos)
        self.assertEqual(executar.call_count, 2)

    def test_cancelamento_interrompe_proximas_etapas(self):
        agente, _, chamadas = agente_simulado()
        ferramenta = agente.executor.registro.obter("localizar_aplicativo")

        def localizar_e_cancelar(nome):
            agente.cancelar()
            return ferramenta.executar(nome)

        agente.executor.registro._ferramentas["localizar_aplicativo"] = Ferramenta(
            ferramenta.nome, ferramenta.descricao, ferramenta.parametros,
            ferramenta.risco, localizar_e_cancelar, ferramenta.verificacao)
        resultado = agente.executar("Prepare meu ambiente de programação.")
        self.assertEqual(resultado.status, StatusAgente.CANCELADO)
        self.assertEqual(chamadas, [("localizar", "vscode")])


if __name__ == "__main__":
    unittest.main()
