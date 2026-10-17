"""Testes do detector em segundo plano (com um detector falso).

Rodar:  python test_segundo_plano.py
"""
import time
import unittest

import numpy as np

from segundo_plano import DetectorEmSegundoPlano

FRAME = np.zeros((10, 10, 3), np.uint8)


class Lento:
    def __init__(self, espera=0.05, falha=False):
        self.espera, self.falha, self.chamadas = espera, falha, 0

    def detectar(self, frame):
        self.chamadas += 1
        time.sleep(self.espera)
        if self.falha:
            raise RuntimeError("falhou")
        return [(0.1, 0.1, 0.3, 0.5, 0.9)]


def esperar(ts, limite=2.0):
    fim = time.time() + limite
    while time.time() < fim:
        r = ts.pegar()
        if r:
            return r
        time.sleep(0.005)
    return None


class TesteSegundoPlano(unittest.TestCase):
    def test_entrega_o_resultado(self):
        ts = DetectorEmSegundoPlano(Lento())
        self.assertTrue(ts.enviar(FRAME, 12.5))
        deteccoes, agora, ms = esperar(ts)
        self.assertEqual(len(deteccoes), 1)
        self.assertEqual(agora, 12.5)
        self.assertGreaterEqual(ms, 40)
        self.assertIsNone(ts.pegar())            # só entrega uma vez
        ts.parar()

    def test_ocupado_ignora_quadros_novos(self):
        det = Lento(0.1)
        ts = DetectorEmSegundoPlano(det)
        self.assertTrue(ts.enviar(FRAME, 1.0))
        self.assertFalse(ts.enviar(FRAME, 2.0))
        esperar(ts)
        self.assertEqual(det.chamadas, 1)
        self.assertTrue(ts.enviar(FRAME, 3.0))   # livre de novo
        ts.parar()

    def test_erro_nao_derruba_e_libera(self):
        det = Lento(0.01, falha=True)
        ts = DetectorEmSegundoPlano(det)
        ts.enviar(FRAME, 1.0)
        time.sleep(0.3)
        self.assertIsNone(ts.pegar())
        self.assertEqual(ts.erros, 1)
        self.assertTrue(ts.enviar(FRAME, 2.0))   # continua aceitando
        ts.parar()

    def test_respeita_o_intervalo_minimo(self):
        ts = DetectorEmSegundoPlano(Lento(0.0), intervalo_min_s=0.3)
        self.assertTrue(ts.enviar(FRAME, 1.0))
        esperar(ts)
        self.assertFalse(ts.enviar(FRAME, 2.0))     # cedo demais
        time.sleep(0.35)
        self.assertTrue(ts.enviar(FRAME, 3.0))
        ts.parar()


if __name__ == "__main__":
    unittest.main(verbosity=2)
