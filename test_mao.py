"""Testes de mao.py (sem câmera nem modelos).

Rodar:  python test_mao.py
"""
import unittest

from mao import (area, centro_da_mao, mao_da_pessoa, pessoa_da_frente,
                 regiao_da_pessoa)
from rastreador import Pista


def pista(i, caixa, visivel=True):
    return Pista(id=i, caixa=caixa, conf=0.9, visivel=visivel)


def mao(cx, cy, r=0.03):
    return [(cx + (i % 5 - 2) * r / 2, cy + (i // 5 - 2) * r / 2)
            for i in range(21)]


class TesteMao(unittest.TestCase):
    def test_frente_e_a_maior_caixa(self):
        longe = pista(1, (0.1, 0.3, 0.2, 0.6))
        perto = pista(2, (0.4, 0.1, 0.8, 0.95))
        self.assertEqual(pessoa_da_frente([longe, perto]).id, 2)

    def test_ignora_quem_sumiu_e_lista_vazia(self):
        self.assertIsNone(pessoa_da_frente([]))
        self.assertIsNone(pessoa_da_frente(
            [pista(1, (0, 0, 1, 1), visivel=False)]))

    def test_regiao_cresce_dos_lados(self):
        x0, y0, x1, y1 = regiao_da_pessoa((0.4, 0.2, 0.6, 0.8))
        self.assertAlmostEqual(x0, 0.32)
        self.assertAlmostEqual(x1, 0.68)
        self.assertAlmostEqual(y0, 0.08)

    def test_mao_dentro_e_fora(self):
        caixa = (0.4, 0.2, 0.6, 0.8)
        self.assertTrue(mao_da_pessoa(mao(0.5, 0.5), caixa))
        self.assertTrue(mao_da_pessoa(mao(0.66, 0.4), caixa))    # braço aberto
        self.assertFalse(mao_da_pessoa(mao(0.9, 0.5), caixa))    # outra pessoa

    def test_entradas_invalidas(self):
        self.assertFalse(mao_da_pessoa(None, (0, 0, 1, 1)))
        self.assertFalse(mao_da_pessoa([(0.5, 0.5)] * 5, (0, 0, 1, 1)))
        self.assertFalse(mao_da_pessoa(mao(0.5, 0.5), None))

    def test_centro(self):
        cx, cy = centro_da_mao(mao(0.3, 0.7))
        self.assertAlmostEqual(cx, 0.3, places=1)
        self.assertAlmostEqual(cy, 0.7, places=1)
        self.assertAlmostEqual(area((0, 0, 0.5, 0.5)), 0.25)


if __name__ == "__main__":
    unittest.main(verbosity=2)
