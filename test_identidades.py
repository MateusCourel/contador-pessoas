"""Testes de identidades.py e estatisticas.py (sem câmera nem modelos).

Rodar:  python test_identidades.py
"""
import os
import tempfile
import unittest

from estatisticas import (Configuracao, HistoricoPorMinuto, MediaMovel,
                          RegistroDeEventos, calcular_cpu, calcular_ram)
from identidades import (GerenteDeIdentidades, associar_rostos,
                         largura_do_rosto)


def malha(nx, ny, meia=0.05):
    """Malha mínima: ponto 1 = nariz, resto espalhado em volta."""
    return [(nx - meia, ny), (nx, ny), (nx + meia, ny)]


class TesteAssociar(unittest.TestCase):
    def test_nariz_dentro_da_caixa(self):
        caixas = {1: (0.1, 0.1, 0.4, 0.9), 2: (0.6, 0.1, 0.9, 0.9)}
        r = associar_rostos([malha(0.75, 0.3)], caixas)
        self.assertEqual(list(r), [2])

    def test_rosto_fora_de_qualquer_caixa(self):
        caixas = {1: (0.1, 0.1, 0.2, 0.2)}
        self.assertEqual(associar_rostos([malha(0.8, 0.8)], caixas), {})

    def test_caixas_sobrepostas_vale_a_menor(self):
        caixas = {1: (0.0, 0.0, 1.0, 1.0), 2: (0.4, 0.2, 0.6, 0.6)}
        r = associar_rostos([malha(0.5, 0.3)], caixas)
        self.assertEqual(list(r), [2])

    def test_malha_vazia_ou_curta(self):
        self.assertEqual(associar_rostos([[], [(0.5, 0.5)]],
                                         {1: (0, 0, 1, 1)}), {})

    def test_largura(self):
        self.assertEqual(largura_do_rosto(malha(0.5, 0.5, 0.1), 1000), 200)
        self.assertEqual(largura_do_rosto([], 1000), 0)


class TesteGerente(unittest.TestCase):
    def test_precisa_de_dois_votos_iguais(self):
        g = GerenteDeIdentidades(votos=2)
        self.assertFalse(g.registrar(1, "Ana", 0.6, 0.0))
        self.assertIsNone(g.nome(1))
        self.assertTrue(g.registrar(1, "Ana", 0.62, 1.0))
        self.assertEqual(g.nome(1), "Ana")
        self.assertEqual(g.rotulo(1), "Ana")

    def test_votos_diferentes_zeram(self):
        g = GerenteDeIdentidades(votos=2)
        g.registrar(1, "Ana", 0.6, 0.0)
        g.registrar(1, "Bia", 0.6, 1.0)
        self.assertIsNone(g.nome(1))
        g.registrar(1, None, 0.2, 2.0)
        g.registrar(1, "Bia", 0.6, 3.0)
        self.assertIsNone(g.nome(1))

    def test_desconhecido_tem_rotulo_com_id(self):
        g = GerenteDeIdentidades()
        self.assertEqual(g.rotulo(7), "Pessoa · ID 7")

    def test_intervalo_entre_tentativas(self):
        g = GerenteDeIdentidades(intervalo_s=0.7)
        self.assertTrue(g.precisa_tentar(1, 0.0))
        g.registrar(1, None, 0.1, 0.0)
        self.assertFalse(g.precisa_tentar(1, 0.3))
        self.assertTrue(g.precisa_tentar(1, 0.8))

    def test_desiste_depois_de_max_tentativas(self):
        g = GerenteDeIdentidades(intervalo_s=0.0, max_tentativas=3)
        for i in range(3):
            g.registrar(1, None, 0.1, float(i))
        self.assertFalse(g.precisa_tentar(1, 10.0))

    def test_para_de_tentar_depois_de_travar(self):
        g = GerenteDeIdentidades(intervalo_s=0.0)
        g.definir(1, "Ana")
        self.assertFalse(g.precisa_tentar(1, 5.0))
        self.assertEqual(g.nome(1), "Ana")

    def test_esquecer_ausentes(self):
        g = GerenteDeIdentidades()
        g.definir(1, "Ana")
        g.definir(2, "Bia")
        g.esquecer_ausentes({2})
        self.assertIsNone(g.nome(1))
        self.assertEqual(g.nome(2), "Bia")


class TesteEstatisticas(unittest.TestCase):
    def test_historico_por_minuto(self):
        h = HistoricoPorMinuto(minutos=5)
        h.registrar(60 * 100 + 5)
        h.registrar(60 * 100 + 10)
        h.registrar(60 * 102 + 1)
        self.assertEqual(h.serie(60 * 102 + 30), [0, 0, 2, 0, 1])

    def test_historico_descarta_antigos(self):
        h = HistoricoPorMinuto(minutos=3)
        h.registrar(0)
        h.registrar(60 * 10)
        self.assertEqual(h.serie(60 * 10), [0, 0, 1])

    def test_media_movel(self):
        m = MediaMovel(alpha=0.5)
        self.assertEqual(m.somar(10), 10)
        self.assertEqual(m.somar(20), 15)

    def test_ram(self):
        txt = "MemTotal:  1000 kB\nMemFree: 100 kB\nMemAvailable:  250 kB\n"
        self.assertAlmostEqual(calcular_ram(txt), 75.0)
        self.assertEqual(calcular_ram(""), 0.0)

    def test_cpu(self):
        self.assertAlmostEqual(calcular_cpu((100, 50), (200, 100)), 50.0)
        self.assertEqual(calcular_cpu((100, 50), (100, 50)), 0.0)

    def test_eventos_csv(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "sub", "eventos.csv")
            r = RegistroDeEventos(caminho)
            r.escrever("entrou", 3)
            r.escrever("saiu", 3)
            linhas = open(caminho, encoding="utf-8").read().splitlines()
            self.assertEqual(linhas[0], "momento,evento,id_rastreio")
            self.assertEqual(len(linhas), 3)
            self.assertTrue(linhas[1].endswith(",entrou,3"))

    def test_configuracao(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "config.json")
            c = Configuracao(caminho)
            self.assertEqual(c.obter("linha", 0.5), 0.5)
            c.definir(linha=0.6, inverter=True)
            c2 = Configuracao(caminho)
            self.assertEqual(c2.obter("linha"), 0.6)
            self.assertTrue(c2.obter("inverter"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
