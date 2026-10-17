"""Testes do ponteiro virtual e da leitura do xwininfo (sem hardware).

Rodar:  python test_ponteiro.py
"""
import unittest

from janelas import interpretar_xwininfo
from ponteiro import Ponteiro


class Falso:
    def __init__(self):
        self.eventos, self.fechado = [], False

    def write(self, tipo, codigo, valor):
        self.eventos.append((tipo, codigo, valor))

    def syn(self):
        pass

    def close(self):
        self.fechado = True


class Ecodes:
    EV_REL, REL_X, REL_Y = 2, 0, 1


class TestePonteiro(unittest.TestCase):
    def novo(self):
        ui = Falso()
        return Ponteiro(lambda: (ui, Ecodes), pausa_inicial_s=0), ui

    def test_direita_soma_positivo(self):
        p, ui = self.novo()
        self.assertTrue(p.disponivel)
        self.assertTrue(p.ir_para_direita())
        self.assertGreater(sum(v for _, _, v in ui.eventos), 3200)

    def test_esquerda_soma_negativo(self):
        p, ui = self.novo()
        p.ir_para_esquerda()
        self.assertLess(sum(v for _, _, v in ui.eventos), -3200)
        self.assertTrue(all(c == Ecodes.REL_X for _, c, _ in ui.eventos))

    def test_fechar(self):
        p, ui = self.novo()
        p.fechar()
        self.assertTrue(ui.fechado)
        self.assertFalse(p.disponivel)
        self.assertFalse(p.ir_para_direita())

    def test_sem_permissao_nao_quebra(self):
        def falha():
            raise PermissionError("negado")
        p = Ponteiro(falha, pausa_inicial_s=0)
        self.assertFalse(p.disponivel)
        self.assertIn("permissão", p.erro)
        self.assertFalse(p.ir_para_esquerda())


class TesteXwininfo(unittest.TestCase):
    def test_le_as_duas_janelas(self):
        texto = ('     0x600010 "TOUCH": ()  1280x800+0+34  +0+34\n'
                 '     0x600006 "TV": ()  1920x1080+1280+0  +1280+0\n'
                 '     0x400001 "outra": ()  100x100+0+0  +0+0\n')
        self.assertEqual(interpretar_xwininfo(texto),
                         {"TOUCH": (1280, 800, 0, 34),
                          "TV": (1920, 1080, 1280, 0)})


if __name__ == "__main__":
    unittest.main(verbosity=2)
