"""Contrato HTTP da janela gráfica com o processador existente."""

import json
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Agent"))

from servicos.comandos_workspace import criar_servidor_comandos


class CanalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.chamadas = []
        self.servidor = criar_servidor_comandos(
            lambda texto: self.chamadas.append(texto) or {"resposta": "Pronto", "aplicacao": "organizer"},
            porta=0,
        )
        self.thread = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        self.thread.join(timeout=2)

    def requisitar(self, metodo, caminho, corpo=None, **headers):
        conexao = HTTPConnection("127.0.0.1", self.servidor.server_address[1], timeout=2)
        try:
            conexao.request(metodo, caminho, body=corpo, headers=headers)
            resposta = conexao.getresponse()
            return resposta.status, json.load(resposta)
        finally:
            conexao.close()

    def test_saude_e_comando_estruturado(self):
        status, dados = self.requisitar("GET", "/health")
        self.assertEqual((status, dados["status"]), (200, "pronta"))
        status, dados = self.requisitar(
            "POST", "/command", json.dumps({"texto": "  abra o Organizador  "}),
            **{"X-Yasmin-Bridge": "workspace-os"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(dados["aplicacao"], "organizer")
        self.assertEqual(self.chamadas, ["abra o Organizador"])

    def test_saude_expoe_estados_sem_conteudo_pessoal(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        self.thread.join(timeout=2)
        self.servidor = criar_servidor_comandos(lambda texto: texto, porta=0,
                                                estado=lambda: {"estado_agente": "interpretando",
                                                                "estado_voz": "escutando_comando"})
        self.thread = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.thread.start()
        status, dados = self.requisitar("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(dados["estado_agente"], "interpretando")
        self.assertNotIn("objetivo", dados)

    def test_pagina_sem_proxy_nao_executa_comando(self):
        corpo = json.dumps({"texto": "excluir arquivos"})
        status, _ = self.requisitar("POST", "/command", corpo)
        self.assertEqual(status, 403)
        status, _ = self.requisitar(
            "POST", "/command", corpo, **{"Origin": "http://evil.test", "X-Yasmin-Bridge": "workspace-os"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.chamadas, [])

    def test_comando_invalido_nao_chega_ao_processador(self):
        status, _ = self.requisitar("POST", "/command", json.dumps({"texto": " "}),
                                   **{"X-Yasmin-Bridge": "workspace-os"})
        self.assertEqual(status, 400)
        self.assertEqual(self.chamadas, [])


if __name__ == "__main__":
    unittest.main()
