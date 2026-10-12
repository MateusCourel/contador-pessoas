"""Testes da lógica de "segurar a mão por 1 segundo". Rodar: python test_gatilho.py"""
import unittest

from gestos import GatilhoPorTempo


def simular(gatilho, eventos):
    """eventos: lista de (tempo_s, ativo). Devolve lista de tempos que dispararam."""
    disparos = []
    for t, ativo in eventos:
        _, disparou = gatilho.update(ativo, agora=t)
        if disparou:
            disparos.append(t)
    return disparos


def quadros(inicio, fim, ativo, passo=0.05):
    n = int(round((fim - inicio) / passo))
    return [(round(inicio + i * passo, 3), ativo) for i in range(n + 1)]


class TesteGatilho(unittest.TestCase):
    def test_dispara_apos_segurar_1s(self):
        g = GatilhoPorTempo(segurar_s=1.0)
        disparos = simular(g, quadros(0, 1.5, True))
        self.assertEqual(len(disparos), 1)
        self.assertAlmostEqual(disparos[0], 1.0, places=1)

    def test_nao_dispara_com_menos_de_1s(self):
        g = GatilhoPorTempo(segurar_s=1.0)
        eventos = quadros(0, 0.8, True) + quadros(0.85, 2.0, False)
        self.assertEqual(simular(g, eventos), [])

    def test_perdoa_falha_curta_da_deteccao(self):
        g = GatilhoPorTempo(segurar_s=1.0, tolerancia_s=0.25)
        eventos = (quadros(0, 0.5, True) + quadros(0.55, 0.65, False)
                   + quadros(0.7, 1.5, True))
        self.assertEqual(len(simular(g, eventos)), 1)

    def test_falha_longa_reinicia_a_contagem(self):
        g = GatilhoPorTempo(segurar_s=1.0, tolerancia_s=0.25)
        eventos = (quadros(0, 0.6, True) + quadros(0.65, 1.2, False)
                   + quadros(1.25, 1.9, True))
        self.assertEqual(simular(g, eventos), [])

    def test_nao_dispara_de_novo_segurando_a_mao(self):
        g = GatilhoPorTempo(segurar_s=1.0, recarga_s=3.0)
        disparos = simular(g, quadros(0, 8.0, True))  # mão parada 8 s
        self.assertEqual(len(disparos), 1)

    def test_dispara_de_novo_depois_de_soltar_e_recarga(self):
        g = GatilhoPorTempo(segurar_s=1.0, recarga_s=3.0)
        eventos = (quadros(0, 1.2, True) + quadros(1.25, 4.5, False)
                   + quadros(4.55, 6.0, True))
        self.assertEqual(len(simular(g, eventos)), 2)

    def test_progresso_cresce_de_0_a_1(self):
        g = GatilhoPorTempo(segurar_s=1.0)
        p0, _ = g.update(True, agora=0.0)
        p1, _ = g.update(True, agora=0.5)
        self.assertEqual(p0, 0.0)
        self.assertAlmostEqual(p1, 0.5, places=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
