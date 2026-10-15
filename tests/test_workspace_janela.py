"""A janela da Yasmin reutiliza o Workspace OS existente."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Agent"))

from interface import janela_workspace


class JanelaWorkspaceTests(unittest.TestCase):
    def test_inicia_workspace_e_abre_janela_propria(self):
        with patch.object(janela_workspace, "_origem", return_value="http://127.0.0.1:8790"), \
             patch.object(janela_workspace, "_ativo", side_effect=[False, True, True]), \
             patch.object(janela_workspace, "_navegador_aplicativo", return_value="C:/Edge/msedge.exe"), \
             patch.object(janela_workspace.subprocess, "Popen") as iniciar:
            self.assertTrue(janela_workspace.abrir_janela())
        self.assertEqual(iniciar.call_count, 2)
        self.assertIn("--no-browser", iniciar.call_args_list[0].args[0])
        self.assertIn("--app=http://127.0.0.1:8790/", iniciar.call_args_list[1].args[0])

    def test_workspace_ja_ativo_nao_e_reiniciado(self):
        with patch.object(janela_workspace, "_origem", return_value="http://127.0.0.1:8790"), \
             patch.object(janela_workspace, "_ativo", return_value=True), \
             patch.object(janela_workspace, "_navegador_aplicativo", return_value="C:/Edge/msedge.exe"), \
             patch.object(janela_workspace.subprocess, "Popen") as iniciar:
            self.assertTrue(janela_workspace.abrir_janela())
        self.assertEqual(iniciar.call_count, 1)


if __name__ == "__main__":
    unittest.main()
