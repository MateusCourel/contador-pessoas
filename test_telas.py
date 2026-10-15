"""Testes da leitura das telas (sem monitor).

Rodar:  python test_telas.py
"""
import unittest

from telas import escolher_telas, interpretar_xrandr

DUAS_TELAS = """\
Screen 0: minimum 320 x 200, current 3200 x 1080, maximum 16384 x 16384
HDMI-A-1 connected primary 1280x800+0+0 (normal left inverted right) 176mm x 110mm
   1280x800      60.00*+
HDMI-A-2 connected 1920x1080+1280+0 (normal left inverted right) 1600mm x 900mm
   1920x1080     60.00*+  50.00
   1280x720      60.00
"""

UMA_TELA_E_UMA_DESLIGADA = """\
HDMI-A-1 connected primary 1280x800+0+0 (normal left inverted right) 176mm x 110mm
   1280x800      60.00*+
HDMI-A-2 disconnected (normal left inverted right)
"""

LIGADA_MAS_DESATIVADA = """\
HDMI-A-1 connected primary 1280x800+0+0 (normal) 176mm x 110mm
HDMI-A-2 connected (normal left inverted right) 1600mm x 900mm
   1920x1080     60.00 +
"""


class TesteTelas(unittest.TestCase):
    def test_duas_telas(self):
        telas = interpretar_xrandr(DUAS_TELAS)
        self.assertEqual(len(telas), 2)
        self.assertEqual(telas[1], {"nome": "HDMI-A-2", "largura": 1920,
                                    "altura": 1080, "x": 1280, "y": 0})

    def test_ignora_desligada(self):
        self.assertEqual(len(interpretar_xrandr(UMA_TELA_E_UMA_DESLIGADA)), 1)

    def test_ignora_ligada_sem_posicao(self):
        # conectada mas ainda sem modo ativo: não tem posição, não conta
        self.assertEqual(len(interpretar_xrandr(LIGADA_MAS_DESATIVADA)), 1)

    def test_escolhe_tv_e_touch(self):
        tv, touch = escolher_telas(interpretar_xrandr(DUAS_TELAS))
        self.assertEqual(tv["largura"], 1920)
        self.assertEqual((touch["largura"], touch["altura"]), (1280, 800))

    def test_uma_tela_so_serve_para_as_duas(self):
        tv, touch = escolher_telas(interpretar_xrandr(UMA_TELA_E_UMA_DESLIGADA))
        self.assertEqual(tv, touch)

    def test_sem_telas(self):
        self.assertEqual(escolher_telas([]), (None, None))

    def test_sem_nenhuma_de_1280x800(self):
        texto = ("A connected 800x480+0+0 (normal)\n"
                 "B connected 1920x1080+800+0 (normal)\n")
        tv, touch = escolher_telas(interpretar_xrandr(texto))
        self.assertEqual((tv["nome"], touch["nome"]), ("B", "A"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
