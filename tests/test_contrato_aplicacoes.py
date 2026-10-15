"""Contrato declarativo das aplicações, sem iniciar serviços."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Agent"))

from agente.integracao_aplicacoes.contrato import ler_contrato
from agente.integracao_aplicacoes.descoberta import descobrir_aplicacoes
from agente.integracao_aplicacoes.estado import observar_aplicacao, registrar_perceptores
from agente.integracao_aplicacoes.ferramentas import registrar_ferramentas_aplicacoes
from agente.ferramentas import Executor, RegistroFerramentas
from agente.modelos import Risco
from agente.percepcao import Percepcao
from agente.verificacao import Verificador
from agente.modelos import Etapa, StatusVerificacao
from agente.modelos import StatusAgente
from agente.nucleo import NucleoAgente
from agente.planejamento import Planejador
from agente.raciocinio import RegrasDeterministicas
from agente.integracao_aplicacoes.raciocinio import RaciocinioAplicacoes
from agente.integracao_aplicacoes.abertura import _url_local, abrir_aplicacao, verificar_abertura


class ContratoAplicacoesTests(unittest.TestCase):
    def test_comandos_abrem_interfaces_pelo_nome_sem_interferir_no_legado(self):
        raiz = Path(__file__).resolve().parents[1] / "applications"
        raciocinio = RaciocinioAplicacoes(RegrasDeterministicas(), raiz)
        exemplos = {
            "Yasmin, abra a Workspace": "workspace-os",
            "Abra o Ink Notebook": "notebook",
            "abra o projeto Analisador de Projetos": "project-analyzer",
            "abra Ink JSON": "json",
        }
        for texto, identificador in exemplos.items():
            with self.subTest(texto=texto):
                objetivo = raciocinio.identificar(texto)
                self.assertEqual(objetivo.parametros["aplicacao"], identificador)
                self.assertEqual(objetivo.tipo, "comando")
        self.assertIsNone(raciocinio.identificar("Abra o VS Code"))
        cadernos = raciocinio.identificar("Yasmin, liste meus cadernos do Ink Notebook")
        self.assertEqual(cadernos.parametros["tipo"], "listar_cadernos_ink")
        plano = Planejador().criar(cadernos, [])
        self.assertEqual([e.ferramenta for e in plano.etapas],
                         ["abrir_aplicacao_ink", "listar_cadernos_ink"])

    def test_leitor_classifica_projeto_real_sem_expor_arquivos_sensiveis(self):
        raiz = Path(__file__).resolve().parents[1] / "applications"
        descoberta = descobrir_aplicacoes(raiz)
        registro, verificador, percepcao = RegistroFerramentas(), Verificador(), Percepcao()
        registrar_ferramentas_aplicacoes(registro, verificador, descoberta, raiz)
        registrar_perceptores(percepcao, descoberta)

        class Memoria:
            def recuperar(self, objetivo, limite=8):
                return []
            def registrar_objetivo(self, objetivo, status):
                pass
            def registrar_experiencia(self, objetivo, aplicativo):
                pass

        agente = NucleoAgente(percepcao, Memoria(),
                             RaciocinioAplicacoes(RegrasDeterministicas(), raiz),
                             Planejador(), registro, verificador)
        with tempfile.TemporaryDirectory() as pasta:
            projeto = Path(pasta)
            (projeto / "MAIN.PY").write_text("print('ok')", encoding="utf-8")
            (projeto / ".env").write_text("PRIVATE", encoding="utf-8")
            (projeto / "private.pem").write_text("PRIVATE", encoding="utf-8")
            (projeto / "secret-folder").mkdir()
            (projeto / "secret-folder" / "hidden.py").write_text("private", encoding="utf-8")
            resultado = agente.executar(f"Yasmin, liste os arquivos do projeto {projeto}")
            self.assertEqual(resultado.status, StatusAgente.CONCLUIDO)
            dados = resultado.estado.ultimo_resultado.resultado
            self.assertEqual(dados["arquivos"], 2)
            self.assertEqual(dados["sensiveis_ignorados"], 2)
            self.assertEqual(dados["amostra"], ["MAIN.PY"])
            self.assertEqual(resultado.estado.etapa_atual.evidencia.status, StatusVerificacao.SUCESSO)
            self.assertEqual(resultado.estado.contexto_imediato["estado_aplicacao"]["aplicacao"],
                             "project-reader")

    def test_abertura_desconhecida_nao_inicia_interface(self):
        raiz = Path(__file__).resolve().parents[1] / "applications"
        resultado = abrir_aplicacao("nao-existe", descobrir_aplicacoes(raiz), raiz)
        self.assertFalse(resultado.sucesso)

    def test_abertura_recusa_endereco_externo_e_reconhece_falha(self):
        self.assertFalse(_url_local("https://example.com/app"))
        self.assertFalse(_url_local("http://127.0.0.1:porta/app"))
        self.assertTrue(_url_local("http://127.0.0.1:8790/app"))
        etapa = Etapa("Abrir", "abrir_aplicacao_ink", {"aplicacao": "json"},
                      verificacao="abertura_aplicacao_ink")
        obs = Percepcao().resultado("abrir_aplicacao_ink", False, {}, "sem navegador")
        self.assertEqual(verificar_abertura(etapa, obs).status, StatusVerificacao.FALHA)

    def test_moldura_notebook_nao_comprova_servico_ativo(self):
        raiz = Path(__file__).resolve().parents[1] / "applications"
        def resposta(url, **kwargs):
            if url.endswith("/api/health"):
                return {"status": "ok", "origin": "http://127.0.0.1:8790"}
            return {"modules": [{"id": "notebook", "installed": True, "enabled": True,
                                 "compatible": True, "url": "/module/notebook/workspace/index.html",
                                 "canStart": False}]}

        with patch("agente.integracao_aplicacoes.abertura._pagina_ativa", return_value=True), \
             patch("agente.integracao_aplicacoes.abertura._saude_local", return_value=False), \
             patch("agente.integracao_aplicacoes.abertura._json", side_effect=resposta), \
             patch("agente.integracao_aplicacoes.abertura._abrir_navegador") as navegador:
            resultado = abrir_aplicacao("notebook", descobrir_aplicacoes(raiz), raiz)
        self.assertFalse(resultado.sucesso)
        self.assertIn("não responde", resultado.erro)
        navegador.assert_not_called()

    def test_descoberta_isola_ids_duplicados(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            dados = {"schemaVersion": 2, "id": "duplicado", "name": "Módulo",
                     "version": "1", "kind": "static-web", "vendor": "Ink-guginha",
                     "author": "Ink-guginha"}
            for nome in ("um", "dois"):
                modulo = raiz / nome
                modulo.mkdir()
                (modulo / "ink-module.json").write_text(json.dumps(dados), encoding="utf-8")
            descoberta = descobrir_aplicacoes(raiz)
            self.assertEqual(len(descoberta.aplicacoes), 1)
            self.assertEqual(len(descoberta.erros), 1)

    def test_objetivo_real_de_analise_percorre_agent_core(self):
        raiz = Path(__file__).resolve().parents[1] / "applications"
        descoberta = descobrir_aplicacoes(raiz)
        registro, verificador, percepcao = RegistroFerramentas(), Verificador(), Percepcao()
        registrar_ferramentas_aplicacoes(registro, verificador, descoberta, raiz)
        registrar_perceptores(percepcao, descoberta)

        class Memoria:
            def recuperar(self, objetivo, limite=8):
                return []

            def registrar_objetivo(self, objetivo, status):
                pass

            def registrar_experiencia(self, objetivo, aplicativo):
                pass

        agente = NucleoAgente(percepcao, Memoria(), RegrasDeterministicas(),
                             Planejador(), registro, verificador)
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta) / "main.py").write_text("print('ok')\n", encoding="utf-8")
            resultado = agente.executar(f'Analise o projeto em "{pasta}"')
            self.assertEqual(resultado.status, StatusAgente.CONCLUIDO)
            self.assertEqual(resultado.estado.ultimo_resultado.resultado["resumo"]["files"], 1)
            self.assertEqual(resultado.estado.etapa_atual.evidencia.status, StatusVerificacao.SUCESSO)
            self.assertEqual(resultado.estado.contexto_imediato["estado_aplicacao"]["aplicacao"],
                             "project-analyzer")

    def test_manifestos_existentes_mantem_identidade(self):
        raiz = Path(__file__).resolve().parents[1] / "applications"
        contratos = [ler_contrato(p) for p in raiz.glob("*/ink-module.json")]
        self.assertGreaterEqual(len(contratos), 15)
        self.assertEqual(len({c.id for c in contratos}), len(contratos))
        self.assertTrue(all(c.fornecedor == c.autor == "Ink-guginha" for c in contratos))

    def test_descoberta_inclui_workspace_e_isola_manifesto_invalido(self):
        raiz = Path(__file__).resolve().parents[1] / "applications"
        descoberta = descobrir_aplicacoes(raiz)
        self.assertEqual(len(descoberta.aplicacoes), 16)
        self.assertEqual(descoberta.erros, ())
        self.assertIn("workspace-os", {c.id for c in descoberta.aplicacoes})

    def test_observacao_estatica_nao_afirma_abertura(self):
        raiz = Path(__file__).resolve().parents[1] / "applications"
        contrato = next(c for c in descobrir_aplicacoes(raiz).aplicacoes if c.id == "json")
        observacao = observar_aplicacao(contrato)
        self.assertTrue(observacao.dados["disponivel"])
        self.assertIsNone(observacao.dados["aberta"])
        self.assertIsNone(observacao.dados["servico_ativo"])

    def test_perceptores_usam_percepcao_existente(self):
        raiz = Path(__file__).resolve().parents[1] / "applications"
        percepcao = Percepcao()
        registrar_perceptores(percepcao, descobrir_aplicacoes(raiz))
        observacao = percepcao.observar("aplicacao:json")
        self.assertEqual(observacao.tipo, "estado_aplicacao")
        self.assertEqual(observacao.dados["fornecedor"], "Ink-guginha")

    def test_ferramentas_utilizam_registro_executor_e_verificador_existentes(self):
        raiz = Path(__file__).resolve().parents[1] / "applications"
        registro, verificador = RegistroFerramentas(), Verificador()
        registrar_ferramentas_aplicacoes(registro, verificador, descobrir_aplicacoes(raiz), raiz)
        self.assertIn("analisar_projeto_ink", {f.nome for f in registro.listar()})
        resultado = Executor(registro).executar("listar_aplicacoes_ink", {})
        self.assertTrue(resultado.sucesso)
        self.assertEqual(len(resultado.resultado["aplicacoes"]), 16)
        etapa = Etapa("Listar aplicações", "listar_aplicacoes_ink", verificacao="catalogo_aplicacoes_ink")
        observacao = Percepcao().resultado(etapa.ferramenta, resultado.sucesso, resultado.resultado, resultado.erro)
        self.assertEqual(verificador.verificar(etapa, observacao).status, StatusVerificacao.SUCESSO)

    def test_analise_real_de_pasta_e_verificada(self):
        raiz = Path(__file__).resolve().parents[1] / "applications"
        registro, verificador = RegistroFerramentas(), Verificador()
        registrar_ferramentas_aplicacoes(registro, verificador, descobrir_aplicacoes(raiz), raiz)
        with tempfile.TemporaryDirectory() as pasta:
            projeto = Path(pasta)
            (projeto / "main.py").write_text("print('ok')\n", encoding="utf-8")
            resultado = Executor(registro).executar("analisar_projeto_ink", {"caminho": str(projeto)})
            self.assertTrue(resultado.sucesso)
            self.assertEqual(resultado.resultado["resumo"]["files"], 1)
            etapa = Etapa("Analisar projeto", "analisar_projeto_ink", {"caminho": str(projeto)},
                          verificacao="analise_projeto_ink")
            observacao = Percepcao().resultado(etapa.ferramenta, resultado.sucesso,
                                              resultado.resultado, resultado.erro)
            self.assertEqual(verificador.verificar(etapa, observacao).status, StatusVerificacao.SUCESSO)

    def test_operacao_exige_risco_e_verificacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            manifesto = Path(pasta) / "ink-module.json"
            dados = {"schemaVersion": 2, "id": "exemplo", "name": "Exemplo",
                     "version": "1.0", "kind": "static-web",
                     "agentOperations": [{"name": "consultar_exemplo", "description": "Consulta",
                                           "parameters": ["termo"], "risk": "baixo",
                                           "verification": "resultado_exemplo"}]}
            manifesto.write_text(json.dumps(dados), encoding="utf-8")
            contrato = ler_contrato(manifesto)
            self.assertEqual(contrato.operacoes[0].risco, Risco.BAIXO)
            del dados["agentOperations"][0]["verification"]
            manifesto.write_text(json.dumps(dados), encoding="utf-8")
            with self.assertRaises(ValueError):
                ler_contrato(manifesto)

    def test_entrada_nao_pode_sair_da_aplicacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            manifesto = Path(pasta) / "ink-module.json"
            manifesto.write_text(json.dumps({"schemaVersion": 2, "id": "exemplo",
                                             "name": "Exemplo", "version": "1.0",
                                             "kind": "static-web", "entryFile": "../fora.html"}),
                                 encoding="utf-8")
            with self.assertRaises(ValueError):
                ler_contrato(manifesto)
