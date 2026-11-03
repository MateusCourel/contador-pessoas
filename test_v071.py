"""Testes da v0.7.1: o nome não pula para outra pessoa."""
import unittest

from identidades import (GerenteDeIdentidades, NOME_FRESCO_S, NOME_SOLTAR_S)
from rastreador import Rastreador


def travar(g, pid, nome="Ana", t=0.0):
    g.registrar(pid, nome, 0.7, t)
    g.registrar(pid, nome, 0.7, t + 0.7)
    return t + 0.7


class TestNomeConfiavel(unittest.TestCase):
    def test_nome_firme_depois_vira_interrogacao_e_depois_solta(self):
        g = GerenteDeIdentidades()
        t = travar(g, 1)
        self.assertTrue(g.firme(1, t + 1))
        self.assertIn("%", g.rotulo_com_confianca(1, t + 1))
        self.assertEqual(g.rotulo_com_confianca(1, t + NOME_FRESCO_S + 1),
                         "Ana · ?")
        self.assertFalse(g.firme(1, t + NOME_FRESCO_S + 1))
        g.expirar(t + NOME_SOLTAR_S + 1)
        self.assertIsNone(g.nome(1))

    def test_conferir_o_rosto_renova(self):
        g = GerenteDeIdentidades()
        t = travar(g, 1)
        g.registrar(1, "Ana", 0.7, t + 3)
        self.assertTrue(g.firme(1, t + 3 + NOME_FRESCO_S - 0.1))
        self.assertEqual(g.expirar(t + NOME_SOLTAR_S), [])

    def test_duvidar_marca_interrogacao_e_antecipa_a_conferencia(self):
        g = GerenteDeIdentidades()
        t = travar(g, 1)
        g.duvidar(1, t + 1)
        self.assertEqual(g.rotulo_com_confianca(1, t + 1), "Ana · ?")
        self.assertTrue(g.precisa_tentar(1, t + 1.6))
        g.registrar(1, "Ana", 0.7, t + 1.6)          # rosto conferido
        self.assertTrue(g.firme(1, t + 1.7))

    def test_perder_tira_o_nome(self):
        g = GerenteDeIdentidades()
        t = travar(g, 1)
        g.perder(1, t + 1)
        self.assertIsNone(g.nome(1))
        self.assertTrue(g.precisa_tentar(1, t + 1))

    def test_rosto_pequeno_pede_tres_votos(self):
        g = GerenteDeIdentidades()
        g.registrar(1, "Ana", 0.7, 0.0, votos=3)
        g.registrar(1, "Ana", 0.7, 1.0, votos=3)
        self.assertIsNone(g.nome(1))
        g.registrar(1, "Ana", 0.7, 2.0, votos=3)
        self.assertEqual(g.nome(1), "Ana")

    def test_rotulo_antigo_continua_igual(self):
        g = GerenteDeIdentidades()
        travar(g, 1)
        self.assertIn("%", g.rotulo_com_confianca(1))


class TestRastreadorSalto(unittest.TestCase):
    def _pista_confirmada(self):
        r = Rastreador()
        box = (0.40, 0.30, 0.55, 0.70, 0.9)
        r.atualizar([box], 0.0)
        r.atualizar([box], 0.1)
        return r, box

    def test_resgate_marca_salto(self):
        r, _ = self._pista_confirmada()
        longe = (0.50, 0.30, 0.65, 0.70, 0.9)         # IoU < 0.25
        pistas = r.atualizar([longe], 0.2)
        self.assertEqual(len(pistas), 1)
        self.assertEqual(pistas[0].salto_em, 0.2)

    def test_ligacao_fraca_marca_duvida(self):
        r, _ = self._pista_confirmada()
        meio = (0.48, 0.30, 0.63, 0.70, 0.9)          # IoU ~0.30
        pistas = r.atualizar([meio], 0.2)
        self.assertEqual(pistas[0].duvida_em, 0.2)
        self.assertLess(pistas[0].salto_em, 0)

    def test_movimento_normal_nao_marca_nada(self):
        r, _ = self._pista_confirmada()
        perto = (0.41, 0.30, 0.56, 0.70, 0.9)
        pistas = r.atualizar([perto], 0.2)
        self.assertLess(pistas[0].salto_em, 0)
        self.assertLess(pistas[0].duvida_em, 0)


if __name__ == "__main__":
    unittest.main()
