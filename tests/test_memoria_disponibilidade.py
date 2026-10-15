"""A indisponibilidade do MySQL não impede ações locais do agente."""

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Agent"))

from agente.modelos import Objetivo
from infraestrutura.memoria_disponibilidade import MemoriaMySQLDisponivel


class RepositorioControlado:
    def __init__(self):
        self.liberar = threading.Event()
        self.preparado = threading.Event()
        self.objetivos = []

    def preparar(self):
        self.liberar.wait(2)
        self.preparado.set()

    def migrar_memorias_existentes(self, pasta):
        return 0

    def recuperar(self, objetivo, limite=8):
        return [{"categoria": "preferencia"}]

    def registrar_objetivo(self, objetivo, status):
        self.objetivos.append(status)

    def registrar_experiencia(self, objetivo, aplicativo):
        pass


class DisponibilidadeTests(unittest.TestCase):
    def test_inicio_nao_espera_banco_e_depois_delega(self):
        repositorio = RepositorioControlado()
        with tempfile.TemporaryDirectory() as pasta:
            inicio = time.monotonic()
            memoria = MemoriaMySQLDisponivel(repositorio, Path(pasta))
            self.assertLess(time.monotonic() - inicio, 0.5)
            objetivo = Objetivo("Abrir Workspace")
            self.assertEqual(memoria.recuperar(objetivo), [])
            repositorio.liberar.set()
            self.assertTrue(memoria._pronta.wait(2))
            self.assertEqual(memoria.recuperar(objetivo), [{"categoria": "preferencia"}])
            memoria.registrar_objetivo(objetivo, "concluido")
            self.assertEqual(repositorio.objetivos, ["concluido"])
            memoria.fechar()

    def test_reconecta_apos_falha_de_consulta(self):
        class RepositorioInstavel(RepositorioControlado):
            def __init__(self):
                super().__init__()
                self.liberar.set()
                self.preparos = 0
                self.falhar = True

            def preparar(self):
                self.preparos += 1

            def recuperar(self, objetivo, limite=8):
                if self.falhar:
                    self.falhar = False
                    raise ConnectionError("conexão perdida")
                return super().recuperar(objetivo, limite)

        repositorio = RepositorioInstavel()
        with tempfile.TemporaryDirectory() as pasta:
            memoria = MemoriaMySQLDisponivel(repositorio, Path(pasta), intervalo_tentativa=0.01)
            self.assertTrue(memoria._pronta.wait(2))
            objetivo = Objetivo("Abrir Workspace")
            self.assertEqual(memoria.recuperar(objetivo), [])
            limite = time.monotonic() + 2
            while (repositorio.preparos < 2 or not memoria.disponivel) and time.monotonic() < limite:
                time.sleep(0.01)
            self.assertGreaterEqual(repositorio.preparos, 2)
            self.assertEqual(memoria.recuperar(objetivo), [{"categoria": "preferencia"}])
            memoria.fechar()


if __name__ == "__main__":
    unittest.main()
