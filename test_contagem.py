"""Testes da contagem de entradas e saídas (sem câmera).

Rodar:  python test_contagem.py
"""
import unittest

from contagem import ContadorDeEntradas


def passo(c, pid, y, x=0.5):
    return c.atualizar({pid: (x, y)})


class TesteContagem(unittest.TestCase):
    def setUp(self):
        # linha horizontal no meio; "lado positivo" = embaixo (y maior)
        self.c = ContadorDeEntradas()

    def test_atravessar_conta_uma_entrada(self):
        passo(self.c, 1, 0.2)
        passo(self.c, 1, 0.4)
        passo(self.c, 1, 0.6)
        passo(self.c, 1, 0.8)
        self.assertEqual((self.c.entraram, self.c.sairam), (1, 0))

    def test_sentido_contrario_conta_saida(self):
        passo(self.c, 1, 0.8)
        passo(self.c, 1, 0.2)
        self.assertEqual((self.c.entraram, self.c.sairam), (0, 1))

    def test_inverter(self):
        c = ContadorDeEntradas(inverter=True)
        passo(c, 1, 0.2)
        passo(c, 1, 0.8)
        self.assertEqual((c.entraram, c.sairam), (0, 1))

    def test_quem_ja_aparece_dentro_nao_conta(self):
        passo(self.c, 1, 0.8)
        passo(self.c, 1, 0.85)
        self.assertEqual(self.c.entraram, 0)

    def test_tremida_na_linha_nao_conta_duas_vezes(self):
        passo(self.c, 1, 0.3)
        for y in (0.49, 0.51, 0.495, 0.505, 0.5):     # dentro do corredor
            passo(self.c, 1, y)
        self.assertEqual(self.c.entraram, 0)
        passo(self.c, 1, 0.7)
        self.assertEqual(self.c.entraram, 1)
        passo(self.c, 1, 0.68)
        passo(self.c, 1, 0.72)
        self.assertEqual(self.c.entraram, 1)

    def test_voltar_atras_antes_de_cruzar_nao_conta(self):
        passo(self.c, 1, 0.3)
        passo(self.c, 1, 0.45)       # chegou perto, mas não passou
        passo(self.c, 1, 0.3)
        self.assertEqual((self.c.entraram, self.c.sairam), (0, 0))

    def test_cruzar_e_voltar_conta_entrada_e_saida(self):
        passo(self.c, 1, 0.3)
        passo(self.c, 1, 0.7)
        passo(self.c, 1, 0.3)
        self.assertEqual((self.c.entraram, self.c.sairam), (1, 1))
        self.assertEqual(self.c.dentro, 0)

    def test_varias_pessoas_independentes(self):
        self.c.atualizar({1: (0.3, 0.2), 2: (0.7, 0.8)})
        eventos = self.c.atualizar({1: (0.3, 0.8), 2: (0.7, 0.2)})
        self.assertCountEqual(eventos, [(1, "entrou"), (2, "saiu")])

    def test_evento_devolvido(self):
        passo(self.c, 7, 0.2)
        self.assertEqual(passo(self.c, 7, 0.9), [(7, "entrou")])

    def test_quem_some_do_quadro_e_esquecido(self):
        passo(self.c, 1, 0.2)
        self.c.atualizar({})                     # sumiu
        passo(self.c, 1, 0.9)                    # mesmo ID volta: é novo
        self.assertEqual(self.c.entraram, 0)

    def test_linha_diagonal(self):
        c = ContadorDeEntradas(ponto_a=(0.0, 0.0), ponto_b=(1.0, 1.0))
        c.atualizar({1: (0.8, 0.2)})              # acima da diagonal
        c.atualizar({1: (0.2, 0.8)})              # abaixo da diagonal
        self.assertEqual(c.entraram + c.sairam, 1)

    def test_pico_e_dentro(self):
        self.c.atualizar({1: (0.5, 0.2), 2: (0.4, 0.2), 3: (0.6, 0.2)})
        self.assertEqual(self.c.pico_na_camera, 3)
        self.c.atualizar({1: (0.5, 0.9)})
        self.assertEqual(self.c.dentro, 1)

    def test_reiniciar(self):
        passo(self.c, 1, 0.2)
        passo(self.c, 1, 0.9)
        self.c.reiniciar()
        self.assertEqual((self.c.entraram, self.c.pico_na_camera), (0, 0))

    def test_mover_linha_nao_conta_ninguem(self):
        self.c.atualizar({1: (0.5, 0.2)})
        self.c.mover_linha((0.0, 0.1), (1.0, 0.1), False)   # sobe a linha
        self.c.atualizar({1: (0.5, 0.2)})                   # agora "abaixo"
        self.assertEqual((self.c.entraram, self.c.sairam), (0, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
