"""Testes da edição do wayfire.ini (sem mexer em arquivo nenhum).

Rodar:  python test_configurar_telas.py
"""
import os
import tempfile
import unittest

from configurar_telas import ajustar, conectores, regras

TV = {"x": 1280, "y": 0, "largura": 1920, "altura": 1080}
TOUCH = {"x": 0, "y": 0, "largura": 1280, "altura": 800}
ORIGINAL = """[core]
plugins = alpha animate autostart command grid

[input-device:TSTP MTouch]
output = HDMI-A-1
"""


class TesteAjustar(unittest.TestCase):
    def setUp(self):
        self.r = regras(TV, TOUCH, "HDMI-A-2", "HDMI-A-1")

    def test_regras(self):
        self.assertIn('set geometry 1280 0 1920 1080', self.r[0])
        self.assertIn('start_on_output "HDMI-A-2"', self.r[1])
        self.assertIn('set geometry 0 0 1280 800', self.r[2])
        self.assertEqual(len(regras(TV, TOUCH, None, None)), 2)

    def test_acrescenta_plugin_e_secao(self):
        novo = ajustar(ORIGINAL, self.r)
        self.assertIn("grid window-rules", novo)
        self.assertIn("[window-rules]", novo)
        self.assertIn("[input-device:TSTP MTouch]", novo)   # não perde nada
        self.assertIn("output = HDMI-A-1", novo)

    def test_idempotente(self):
        uma = ajustar(ORIGINAL, self.r)
        duas = ajustar(uma, self.r)
        self.assertEqual(uma, duas)
        self.assertEqual(duas.count("tv_pos"), 1)
        self.assertEqual(duas.count("window-rules"), 2)  # plugin + seção

    def test_plugin_ja_presente(self):
        base = ORIGINAL.replace("grid", "grid window-rules")
        novo = ajustar(base, self.r)
        self.assertEqual(novo.count("grid window-rules"), 1)

    def test_secao_existente_recebe_as_regras(self):
        base = ORIGINAL + "\n[window-rules]\noutra = on created then maximize\n"
        novo = ajustar(base, self.r)
        self.assertEqual(novo.count("[window-rules]"), 1)
        self.assertIn("outra = on created then maximize", novo)
        self.assertIn("tv_pos", novo)

    def test_atualiza_regra_antiga(self):
        uma = ajustar(ORIGINAL, self.r)
        outra = regras({**TV, "x": 1500}, TOUCH, "HDMI-A-2", "HDMI-A-1")
        duas = ajustar(uma, outra)
        self.assertIn("set geometry 1500 0", duas)
        self.assertNotIn("set geometry 1280 0 1920", duas)


class TesteConectores(unittest.TestCase):
    def test_le_o_drm(self):
        with tempfile.TemporaryDirectory() as p:
            for nome, status, modo in (("card1-HDMI-A-1", "connected",
                                        "1280x800\n1024x768\n"),
                                       ("card1-HDMI-A-2", "connected",
                                        "1920x1080\n"),
                                       ("card1-DSI-1", "disconnected", ""),
                                       ("card1-HDMI-A-3", "disconnected", "")):
                os.makedirs(os.path.join(p, nome))
                open(os.path.join(p, nome, "status"), "w").write(status + "\n")
                open(os.path.join(p, nome, "modes"), "w").write(modo)
            self.assertEqual(conectores(p), {"HDMI-A-1": "1280x800",
                                             "HDMI-A-2": "1920x1080"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
