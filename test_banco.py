"""Testes do banco e da montagem dos pontos do rosto (sem câmera e sem modelo).

Rodar:  python test_banco.py
"""
import unittest

import numpy as np

from banco import Banco
from embeddings import face_para_sface


def vetor(seed, ruido=0.0):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=128)
    if ruido:
        v = v + np.random.default_rng(seed + 1000).normal(size=128) * ruido
    return v.astype(np.float32)


class TesteBanco(unittest.TestCase):
    def setUp(self):
        self.b = Banco(":memory:")

    def test_cadastra_e_lista(self):
        pid = self.b.cadastrar("Ana", {"centro": vetor(1), "cima": vetor(2)})
        linhas = self.b.listar()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0][0], pid)
        self.assertEqual(linhas[0][1], "Ana")
        self.assertEqual(linhas[0][3], 2)

    def test_reconhece_a_mesma_pessoa(self):
        self.b.cadastrar("Ana", {"centro": vetor(1)})
        self.b.cadastrar("Bruno", {"centro": vetor(2)})
        nome, sim = self.b.identificar(vetor(1, ruido=0.3))
        self.assertEqual(nome, "Ana")
        self.assertGreater(sim, 0.363)

    def test_desconhecido(self):
        self.b.cadastrar("Ana", {"centro": vetor(1)})
        nome, _ = self.b.identificar(vetor(99))
        self.assertIsNone(nome)

    def test_banco_vazio(self):
        self.assertEqual(self.b.identificar(vetor(1)), (None, 0.0))

    def test_apagar_remove_tudo(self):
        pid = self.b.cadastrar("Ana", {"centro": vetor(1), "cima": vetor(2)})
        self.assertTrue(self.b.apagar(pid))
        self.assertEqual(self.b.listar(), [])
        n = self.b._con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        self.assertEqual(n, 0)
        self.assertFalse(self.b.apagar(pid))
        self.assertEqual(self.b.identificar(vetor(1)), (None, 0.0))

    def test_recusa_nome_vazio_ou_sem_consentimento(self):
        with self.assertRaises(ValueError):
            self.b.cadastrar("  ", {"centro": vetor(1)})
        with self.assertRaises(ValueError):
            self.b.cadastrar("Ana", {})
        with self.assertRaises(ValueError):
            self.b.cadastrar("Ana", {"centro": vetor(1)}, consentimento=False)


class TesteFaceSface(unittest.TestCase):
    def malha(self, largura_rosto=0.3):
        p = [(0.5, 0.5)] * 478
        p = list(p)
        p[234] = (0.5 - largura_rosto / 2, 0.5)
        p[454] = (0.5 + largura_rosto / 2, 0.5)
        p[10] = (0.5, 0.2)
        p[152] = (0.5, 0.8)
        return p

    def test_formato(self):
        f = face_para_sface(self.malha(), 1280, 720)
        self.assertEqual(f.shape, (1, 15))
        self.assertEqual(f.dtype, np.float32)

    def test_rosto_pequeno_demais(self):
        self.assertIsNone(face_para_sface(self.malha(0.03), 1280, 720))

    def test_sem_pontos(self):
        self.assertIsNone(face_para_sface(None, 1280, 720))
        self.assertIsNone(face_para_sface([(0.5, 0.5)] * 10, 1280, 720))


if __name__ == "__main__":
    unittest.main(verbosity=2)
