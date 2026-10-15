"""Testes do teclado virtual (sem tela e sem câmera).

Rodar:  python test_teclado.py
"""
import unittest

import numpy as np

from teclado import TecladoVirtual, sem_acentos


def toque(t, rotulo):
    """Simula um toque no centro do botão com esse rótulo."""
    b = next(b for b in t._botoes if b["rotulo"] == rotulo)
    return t.tocar(b["x"] + b["w"] // 2, b["y"] + b["h"] // 2)


def digita(t, *rotulos):
    for r in rotulos:
        toque(t, r)


class TesteTeclado(unittest.TestCase):
    def setUp(self):
        self.t = TecladoVirtual()

    def test_primeira_letra_maiuscula_e_resto_minusculo(self):
        digita(self.t, "M", "A", "T")
        self.assertEqual(self.t.texto, "Mat")

    def test_nova_palavra_comeca_maiuscula(self):
        digita(self.t, "A", "N", "A", "ESPACO", "L", "U", "Z")
        self.assertEqual(self.t.texto, "Ana Luz")

    def test_shift_vale_para_uma_letra(self):
        digita(self.t, "A", "SHIFT", "B", "C")
        self.assertEqual(self.t.texto, "ABc")

    def test_acento_til(self):
        digita(self.t, "J", "O", "~", "A", "O")
        self.assertEqual(self.t.texto, "João")

    def test_acento_agudo_em_maiuscula(self):
        digita(self.t, "´", "E")        # início do nome: maiúscula
        self.assertEqual(self.t.texto, "É")

    def test_acento_circunflexo_e_crase(self):
        digita(self.t, "V", "O", "^", "O", "ESPACO", "A", "`", "A")
        self.assertEqual(self.t.texto, "Voô Aà")

    def test_acento_em_consoante_e_ignorado(self):
        digita(self.t, "A", "~", "B")
        self.assertEqual(self.t.texto, "Ab")
        self.assertIsNone(self.t.acento)

    def test_tocar_acento_duas_vezes_cancela(self):
        digita(self.t, "A", "~", "~", "O")
        self.assertEqual(self.t.texto, "Ao")

    def test_cedilha(self):
        digita(self.t, "A", "Ç")
        self.assertEqual(self.t.texto, "Aç")

    def test_apagar(self):
        digita(self.t, "A", "B", "APAGAR")
        self.assertEqual(self.t.texto, "A")
        digita(self.t, "APAGAR", "APAGAR")      # apagar com vazio não quebra
        self.assertEqual(self.t.texto, "")

    def test_espaco_nao_duplica_nem_vem_no_comeco(self):
        digita(self.t, "ESPACO", "A", "ESPACO", "ESPACO", "B")
        self.assertEqual(self.t.texto, "A B")

    def test_limite_de_tamanho(self):
        t = TecladoVirtual(max_chars=3)
        digita(t, "A", "B", "C", "D")
        self.assertEqual(t.texto, "Abc")

    def test_teclado_fisico(self):
        for c in "ana  maria":
            self.t.digitar_tecla(c)
        self.assertEqual(self.t.texto, "Ana Maria")

    def test_ok_e_cancelar(self):
        self.assertEqual(toque(self.t, "OK"), "ok")
        self.assertEqual(toque(self.t, "CANCELAR"), "cancelar")

    def test_toque_fora_das_teclas(self):
        self.assertIsNone(self.t.tocar(5, 5))
        self.assertEqual(self.t.texto, "")

    def test_teclas_dentro_da_tela_e_sem_sobreposicao(self):
        bs = self.t._botoes
        for b in bs:
            self.assertGreaterEqual(b["x"], 0)
            self.assertLessEqual(b["x"] + b["w"], self.t.largura)
            self.assertLessEqual(b["y"] + b["h"], self.t.altura)
        for i, a in enumerate(bs):
            for b in bs[i + 1:]:
                sobrepoe = (a["x"] < b["x"] + b["w"] and
                            b["x"] < a["x"] + a["w"] and
                            a["y"] < b["y"] + b["h"] and
                            b["y"] < a["y"] + a["h"])
                self.assertFalse(sobrepoe, (a["rotulo"], b["rotulo"]))

    def test_desenha_sem_erro(self):
        frame = np.full((720, 1280, 3), 120, np.uint8)
        digita(self.t, "J", "O", "~", "A", "O")
        self.t.desenhar(frame)
        self.assertEqual(frame.shape, (720, 1280, 3))
        self.t._usa_pil = False          # plano B sem Pillow
        self.t.desenhar(frame)

    def test_sem_acentos(self):
        self.assertEqual(sem_acentos("João Ção"), "Joao Cao")


if __name__ == "__main__":
    unittest.main(verbosity=2)
