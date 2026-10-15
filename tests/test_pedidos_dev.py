"""Objetivos de desenvolvimento com ferramentas reais e verificação de arquivos."""

import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "Agent"))

from agente.ferramentas import Ferramenta, RegistroFerramentas
from agente.decisao import DecisorInteracao
from agente.integracao_aplicacoes.descoberta import descobrir_aplicacoes
from agente.integracao_aplicacoes.ferramentas import registrar_ferramentas_aplicacoes
from agente.integracao_aplicacoes.leitor import exportar_contexto, verificar_exportacao
from agente.modelos import (Etapa, Observacao, ResultadoFerramenta,
                           Objetivo, ResultadoVerificacao, Risco,
                           StatusAgente, StatusEtapa, StatusVerificacao)
from agente.nucleo import NucleoAgente
from agente.pedidos_dev import RaciocinioDev
from agente.planos_ferramentas import objetivo_de_proposta
from agente.percepcao import Percepcao
from agente.planejamento import Planejador
from agente.raciocinio import RegrasDeterministicas
from agente.verificacao import Verificador
import audio_yasm as audio


class MemoriaVazia:
    def recuperar(self, objetivo, limite=8):
        return []

    def registrar_objetivo(self, objetivo, status):
        pass

    def registrar_experiencia(self, objetivo, aplicativo):
        pass


class PedidosDevTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        self.projeto = self.raiz / "projeto-demo"
        self.projeto.mkdir()
        (self.projeto / "main.py").write_text("print('olá')\n", encoding="utf-8")
        (self.projeto / "pyproject.toml").write_text(
            '[project]\nname = "projeto-demo"\nversion = "0.1.0"\n'
            'description = "Ferramenta de exemplo para gerar relatórios."\n', encoding="utf-8")
        self.destino = self.raiz / "saida"
        self.destino.mkdir()
        self.raciocinio = RaciocinioDev(RegrasDeterministicas())
        self.descoberta = descobrir_aplicacoes(RAIZ / "applications")

    def test_interpreta_pedidos_compostos_com_caminhos(self):
        origem, destino = str(self.projeto), str(self.destino)
        exportar = self.raciocinio.identificar(
            f'Yasmin, abra o Leitor de Projetos, faça ele gerar o resumo de "{origem}" e coloque na pasta "{destino}"')
        self.assertEqual(exportar.parametros["tipo"], "exportar_contexto_projeto_ink")
        self.assertEqual(exportar.parametros["destino"], destino)
        readme = self.raciocinio.identificar(
            f'Gere um README com nome GUIA.md na pasta "{origem}" explicando o projeto')
        self.assertEqual((readme.parametros["tipo"], readme.parametros["nome"]),
                         ("gerar_readme_projeto", "GUIA.md"))
        sem_extensao = self.raciocinio.identificar(
            f'Crie um README chamado DOCUMENTACAO na pasta "{origem}"')
        self.assertEqual(sem_extensao.parametros["nome"], "DOCUMENTACAO.md")
        leitura = self.raciocinio.identificar(f'Leia o projeto "{origem}" e me diga o que ele faz')
        self.assertEqual(leitura.parametros["tipo"], "descrever_projeto")
        self.assertIsNone(self.raciocinio.identificar("Gere um README em uma pasta qualquer"))
        self.assertEqual(DecisorInteracao(self.raciocinio).decidir(
            "Gere um README em uma pasta qualquer").via, "esclarecer")
        estranho = DecisorInteracao(self.raciocinio).decidir(
            f'Gere um README na pasta "{origem}" e depois abra o navegador')
        self.assertEqual(estranho.via, "esclarecer")
        estranho_sem_depois = DecisorInteracao(self.raciocinio).decidir(
            f'Gere um README na pasta "{origem}" e abra o navegador')
        self.assertEqual(estranho_sem_depois.via, "esclarecer")

    def test_readme_percorre_core_e_nao_sobrescreve(self):
        registro, verificador = RegistroFerramentas(), Verificador()
        registrar_ferramentas_aplicacoes(registro, verificador, self.descoberta, RAIZ / "applications")
        agente = NucleoAgente(Percepcao(), MemoriaVazia(), self.raciocinio,
                             Planejador(), registro, verificador)
        texto = f'Gere um README com nome GUIA.md na pasta "{self.projeto}" explicando o projeto'
        resultado = agente.executar(texto)
        self.assertEqual(resultado.status, StatusAgente.CONCLUIDO, resultado.mensagem)
        arquivo = self.projeto / "GUIA.md"
        self.assertIn("Ferramenta de exemplo", arquivo.read_text(encoding="utf-8"))
        self.assertEqual(len(resultado.estado.plano_atual.etapas), 2)
        self.assertTrue(all(etapa.evidencia.status == StatusVerificacao.SUCESSO
                            for etapa in resultado.estado.plano_atual.etapas))
        segunda = agente.executar(texto)
        self.assertEqual(segunda.status, StatusAgente.FALHOU)
        self.assertIn("não sobrescrevi", segunda.mensagem)

    def test_variacoes_de_linguagem_e_destino_independente(self):
        origem, destino = str(self.projeto), str(self.destino)
        frases = (
            (f'Documente o repositório "{origem}" num arquivo GUIA.md dentro da pasta "{destino}"',
             "gerar_readme_projeto"),
            (f'Crie um README chamado GUIA.md na pasta "{destino}" explicando o projeto "{origem}"',
             "gerar_readme_projeto"),
            (f'Monte um relatório resumido do projeto "{origem}" e salve na pasta "{destino}"',
             "resumir_projeto_em_arquivo"),
            (f'Entenda o código "{origem}" e me explique para que serve',
             "descrever_projeto"),
            (f'Leia o projeto {origem} e me diga o que ele faz',
             "descrever_projeto"),
        )
        for frase, tipo in frases:
            with self.subTest(frase=frase):
                objetivo = self.raciocinio.identificar(frase)
                self.assertIsNotNone(objetivo)
                self.assertEqual(objetivo.parametros["tipo"], tipo)
                self.assertEqual(objetivo.parametros["caminho"], origem)
                if tipo != "descrever_projeto":
                    self.assertEqual(objetivo.parametros["destino"], destino)

    def test_plano_proposto_usa_registro_real_e_rejeita_ferramenta_inventada(self):
        registro, verificador = RegistroFerramentas(), Verificador()
        registrar_ferramentas_aplicacoes(registro, verificador, self.descoberta, RAIZ / "applications")
        origem, destino = str(self.projeto), str(self.destino)
        texto = f'Levante a arquitetura do repositório "{origem}" e entregue GUIA.md em "{destino}"'
        proposta = {"etapas": [
            {"ferramenta": "analisar_projeto_ink", "parametros": {"caminho": origem}},
            {"ferramenta": "escrever_resumo_projeto", "parametros": {
                "caminho": origem, "destino": destino, "nome": "GUIA.md"}},
        ]}

        class Proponente:
            def propor_plano(self, pedido, ferramentas):
                self.assert_tools = ferramentas
                return proposta

        motor = Proponente()
        decisao = DecisorInteracao(self.raciocinio, motor, registro).decidir(texto)
        self.assertEqual(decisao.via, "objetivo")
        self.assertEqual(decisao.objetivo.parametros["tipo"], "plano_ferramentas")
        self.assertIn("escrever_resumo_projeto", motor.assert_tools)
        agente = NucleoAgente(Percepcao(), MemoriaVazia(), self.raciocinio,
                             Planejador(registro), registro, verificador)
        resultado = agente.executar(texto, decisao.objetivo)
        self.assertEqual(resultado.status, StatusAgente.CONCLUIDO, resultado.mensagem)
        self.assertTrue((self.destino / "GUIA.md").is_file())
        self.assertTrue(all(etapa.evidencia.status == StatusVerificacao.SUCESSO
                            for etapa in resultado.estado.plano_atual.etapas))
        invalida = {"etapas": [{"ferramenta": "apagar_tudo", "parametros": {}}]}
        self.assertIsNone(objetivo_de_proposta(texto, invalida, registro))
        inventado = {"etapas": [{"ferramenta": "analisar_projeto_ink",
                                   "parametros": {"caminho": str(self.raiz / "inventado")}}]}
        self.assertIsNone(objetivo_de_proposta(texto, inventado, registro))
        incompleto = {"etapas": [{"ferramenta": "analisar_projeto_ink",
                                   "parametros": {"caminho": origem}}]}
        self.assertIsNone(objetivo_de_proposta(
            f'Abra o Leitor de Projetos e analise "{origem}"', incompleto, registro))

    def test_composicao_local_seleciona_tres_ferramentas_reais(self):
        registro, verificador = RegistroFerramentas(), Verificador()
        registrar_ferramentas_aplicacoes(registro, verificador, self.descoberta, RAIZ / "applications")
        origem, destino = str(self.projeto), str(self.destino)
        frase = (f'Inspecione o repositório "{origem}", liste os arquivos e '
                 f'grave um guia chamado GUIA.md na pasta "{destino}"')
        decisao = DecisorInteracao(self.raciocinio, ferramentas=registro).decidir(frase)
        self.assertEqual(decisao.via, "objetivo")
        self.assertEqual(decisao.origem, "composicao_local")
        agente = NucleoAgente(Percepcao(), MemoriaVazia(), self.raciocinio,
                             Planejador(registro), registro, verificador)
        resultado = agente.executar(frase, decisao.objetivo)
        self.assertEqual(resultado.status, StatusAgente.CONCLUIDO, resultado.mensagem)
        self.assertEqual([etapa.ferramenta for etapa in resultado.estado.plano_atual.etapas],
                         ["analisar_projeto_ink", "listar_arquivos_projeto_ink",
                          "escrever_resumo_projeto"])
        self.assertTrue((self.destino / "GUIA.md").is_file())
        com_readme = DecisorInteracao(self.raciocinio, ferramentas=registro).decidir(
            f'Liste os arquivos do projeto "{origem}" e crie README.md na pasta "{destino}"')
        self.assertEqual(com_readme.via, "objetivo")
        self.assertEqual([item["ferramenta"] for item in com_readme.objetivo.parametros["etapas"]],
                         ["listar_arquivos_projeto_ink", "escrever_resumo_projeto"])
        com_guia = DecisorInteracao(self.raciocinio, ferramentas=registro).decidir(
            f'Inspecione o repositório "{origem}" e grave um guia na pasta "{destino}"')
        self.assertEqual(com_guia.via, "objetivo")
        self.assertEqual(com_guia.objetivo.parametros["etapas"][-1]["parametros"]["nome"],
                         "resumo_projeto.md")
        fora_escopo = DecisorInteracao(self.raciocinio, ferramentas=registro).decidir(
            f'Inspecione o repositório "{origem}" e execute os testes')
        self.assertEqual(fora_escopo.via, "esclarecer")

    def test_frase_reconhecida_pelo_google_chega_ao_plano_verificado(self):
        registro, verificador = RegistroFerramentas(), Verificador()
        registrar_ferramentas_aplicacoes(registro, verificador, self.descoberta, RAIZ / "applications")
        frase = (f"Yasmin, inspecione o repositório {self.projeto} e "
                 f"grave GUIA.md na pasta {self.destino}")
        with patch.object(audio, "WAKE_MOTOR", "google"), patch.object(
            audio, "_preparado", True
        ), patch.object(audio, "gravar_com_sounddevice", return_value=object()), patch.object(
            audio, "transcrever_audio", return_value=audio.ResultadoEscuta(1, frase, "ok", "google")
        ):
            comando = audio.aguardar_ativacao()
        decisao = DecisorInteracao(self.raciocinio, ferramentas=registro).decidir(comando)
        self.assertEqual(decisao.via, "objetivo")
        agente = NucleoAgente(Percepcao(), MemoriaVazia(), self.raciocinio,
                             Planejador(registro), registro, verificador)
        resultado = agente.executar(comando, decisao.objetivo)
        self.assertEqual(resultado.status, StatusAgente.CONCLUIDO, resultado.mensagem)
        self.assertTrue((self.destino / "GUIA.md").is_file())
        self.assertTrue(all(etapa.evidencia.status == StatusVerificacao.SUCESSO
                            for etapa in resultado.estado.plano_atual.etapas))

    def test_progresso_da_etapa_fica_visivel_durante_execucao(self):
        iniciou, liberar = threading.Event(), threading.Event()
        registro, verificador = RegistroFerramentas(), Verificador()

        def executar():
            iniciou.set()
            if not liberar.wait(3):
                return ResultadoFerramenta(False, erro="Prazo excedido")
            return ResultadoFerramenta(True, {"mensagem": "Concluído"})

        registro.registrar(Ferramenta("tarefa_teste", "Executar tarefa de teste", (),
                                     Risco.BAIXO, executar, "tarefa_teste"))
        verificador.registrar("tarefa_teste", lambda etapa, obs: ResultadoVerificacao(
            StatusVerificacao.SUCESSO if obs.dados.get("sucesso") else StatusVerificacao.FALHA,
            1.0, ("Execução observada",)))
        agente = NucleoAgente(Percepcao(), MemoriaVazia(), self.raciocinio,
                             Planejador(registro), registro, verificador)
        objetivo = Objetivo("Teste", parametros={"tipo": "plano_ferramentas", "etapas": [
            {"ferramenta": "tarefa_teste", "parametros": {}}]})
        saida = []
        worker = threading.Thread(target=lambda: saida.append(agente.executar("Teste", objetivo)))
        worker.start()
        try:
            self.assertTrue(iniciou.wait(2))
            self.assertEqual(agente.estado.tarefa_atual, "Executar tarefa de teste")
            self.assertEqual(agente.estado.processos[-1]["status"], "executando")
        finally:
            liberar.set()
            worker.join(3)
        self.assertEqual(saida[0].status, StatusAgente.CONCLUIDO)
        self.assertIn({"descricao": "Executar tarefa de teste", "status": "concluido"},
                      agente.estado.processos)

    def test_leitor_exporta_contexto_real_e_verifica(self):
        leitor = next(app for app in self.descoberta.aplicacoes if app.id == "project-reader")
        with patch.dict(os.environ, {"APPDATA": str(self.raiz / "config")}, clear=False):
            resultado = exportar_contexto(leitor, str(self.projeto), str(self.destino))
        self.assertTrue(resultado.sucesso, resultado.erro)
        etapa = Etapa("Exportar", "exportar_contexto_projeto_ink",
                      {"caminho": str(self.projeto), "destino": str(self.destino)})
        observacao = Observacao("resultado", "teste", {"sucesso": True,
                                                          "resultado": resultado.resultado})
        self.assertEqual(verificar_exportacao(leitor, etapa, observacao).status,
                         StatusVerificacao.SUCESSO)
        self.assertTrue((Path(resultado.resultado["destino"]) / ".leitor-ia").is_file())

    def test_resumo_existente_gera_outra_etapa_sem_sobrescrever(self):
        origem, destino = str(self.projeto), str(self.destino)
        objetivo = self.raciocinio.identificar(
            f'Abra o Leitor de Projetos e gere o resumo de "{origem}" na pasta "{destino}"')
        planejador = Planejador()
        plano = planejador.criar(objetivo, [])
        falha = plano.etapas[-1]
        falha.status = StatusEtapa.FALHOU
        falha.resultado = ResultadoFerramenta(False, erro="O arquivo já existe; não sobrescrevi")
        self.assertTrue(planejador.replanejar(plano, falha, objetivo))
        self.assertEqual(plano.etapas[-1].parametros["nome"], "resumo_projeto_2.md")
        self.assertEqual(plano.revisao, 1)
        outro = self.raciocinio.identificar(
            f'Monte um relatório resumido do projeto "{origem}" e salve na pasta "{destino}"')
        plano_outro = planejador.criar(outro, [])
        etapa_outro = plano_outro.etapas[-1]
        etapa_outro.status = StatusEtapa.FALHOU
        etapa_outro.resultado = ResultadoFerramenta(False, erro="O arquivo já existe; não sobrescrevi")
        self.assertTrue(planejador.replanejar(plano_outro, etapa_outro, outro))
        self.assertEqual(plano_outro.etapas[-1].parametros["nome"], "resumo_projeto_2.md")


if __name__ == "__main__":
    unittest.main()
