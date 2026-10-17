"""Testes do rastreador e da leitura da resposta do YOLO (sem modelo e sem
câmera).

Rodar:  python test_rastreador.py
"""
import unittest

import numpy as np

from deteccao import decodificar, preparar_imagem
from rastreador import Rastreador, iou


def caixa(cx, cy=0.5, w=0.2, h=0.6, conf=0.8):
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, conf)


class TesteIou(unittest.TestCase):
    def test_iguais_e_separadas(self):
        a = (0.1, 0.1, 0.3, 0.5)
        self.assertAlmostEqual(iou(a, a), 1.0)
        self.assertEqual(iou(a, (0.6, 0.6, 0.9, 0.9)), 0.0)

    def test_metade(self):
        self.assertAlmostEqual(iou((0, 0, 1, 1), (0.5, 0, 1.5, 1)), 1 / 3)


class TesteRastreador(unittest.TestCase):
    def test_pessoa_nova_so_aparece_depois_de_confirmada(self):
        r = Rastreador(confirmar=2)
        self.assertEqual(r.atualizar([caixa(0.5)], 0.0), [])
        pistas = r.atualizar([caixa(0.5)], 0.05)
        self.assertEqual(len(pistas), 1)

    def test_mantem_o_id_andando(self):
        r = Rastreador()
        ids = set()
        for i in range(30):
            pistas = r.atualizar([caixa(0.2 + i * 0.01)], i * 0.05)
            ids.update(p.id for p in pistas)
        self.assertEqual(ids, {1})

    def test_duas_pessoas_ids_diferentes(self):
        r = Rastreador()
        for i in range(5):
            pistas = r.atualizar([caixa(0.2), caixa(0.7)], i * 0.05)
        self.assertEqual(sorted(p.id for p in pistas), [1, 2])

    def test_perde_por_pouco_tempo_e_mantem_o_id(self):
        r = Rastreador()
        for i in range(4):
            r.atualizar([caixa(0.5)], i * 0.05)
        sumida = r.atualizar([], 0.25)
        self.assertEqual(len(sumida), 1)
        self.assertFalse(sumida[0].visivel)
        volta = r.atualizar([caixa(0.5)], 0.3)
        self.assertEqual([p.id for p in volta], [1])
        self.assertTrue(volta[0].visivel)

    def test_esquece_depois_de_muito_tempo(self):
        r = Rastreador(guardar_s=1.0)
        for i in range(4):
            r.atualizar([caixa(0.5)], i * 0.05)
        self.assertEqual(r.atualizar([], 3.0), [])
        pistas = r.atualizar([caixa(0.5)], 3.05)
        pistas = r.atualizar([caixa(0.5)], 3.10)
        self.assertEqual([p.id for p in pistas], [2])    # ID novo

    def test_vulto_de_um_quadro_nao_vira_pessoa(self):
        r = Rastreador()
        r.atualizar([caixa(0.5)], 0.0)
        self.assertEqual(r.atualizar([], 0.05), [])
        self.assertEqual(r.atualizar([], 0.6), [])

    def test_deteccao_fraca_recupera_quem_ja_existia(self):
        r = Rastreador()
        for i in range(4):
            r.atualizar([caixa(0.5)], i * 0.05)
        pistas = r.atualizar([caixa(0.5, conf=0.2)], 0.2)
        self.assertTrue(pistas[0].visivel)

    def test_deteccao_fraca_sozinha_nao_cria_pessoa(self):
        r = Rastreador()
        for i in range(5):
            pistas = r.atualizar([caixa(0.5, conf=0.2)], i * 0.05)
        self.assertEqual(pistas, [])

    def test_nao_troca_ids_ao_cruzar_proximo(self):
        r = Rastreador()
        ids_esq = ids_dir = None
        for i in range(40):
            a = 0.2 + i * 0.015            # vai da esquerda para a direita
            b = 0.8 - i * 0.015            # e o outro, ao contrário
            pistas = r.atualizar([caixa(a), caixa(b)], i * 0.05)
            if i == 3:
                por_x = sorted(pistas, key=lambda p: p.centro[0])
                ids_esq, ids_dir = por_x[0].id, por_x[1].id
        final = {p.id: p.centro[0] for p in pistas}
        self.assertGreater(final[ids_esq], 0.7)      # quem começou à esquerda
        self.assertLess(final[ids_dir], 0.3)

    def test_pes_e_altura(self):
        r = Rastreador()
        for i in range(3):
            pistas = r.atualizar([(0.4, 0.2, 0.6, 0.8, 0.9)], i * 0.05)
        p = pistas[0]
        self.assertAlmostEqual(p.pes[0], 0.5)
        self.assertAlmostEqual(p.pes[1], 0.8)
        self.assertAlmostEqual(p.altura, 0.6)


class TesteDecodificar(unittest.TestCase):
    def saida_falsa(self, deteccoes, n=2100):
        """Monta uma saída (84, n) como a do modelo, com as caixas dadas
        (cx, cy, w, h, nota) em pixels de 320x320."""
        s = np.zeros((84, n), np.float32)
        for k, (cx, cy, w, h, nota) in enumerate(deteccoes):
            s[0:4, k] = (cx, cy, w, h)
            s[4, k] = nota
        return s

    def test_imagem_16_por_9_vira_quadrada_com_bordas(self):
        frame = np.zeros((720, 1280, 3), np.uint8)
        img, escala, dx, dy = preparar_imagem(frame, 320)
        self.assertEqual(img.shape, (320, 320, 3))
        self.assertAlmostEqual(escala, 0.25)
        self.assertEqual((dx, dy), (0, 70))

    def test_volta_para_coordenadas_da_imagem_original(self):
        # pessoa no centro da imagem original: ocupa o meio da área útil
        s = self.saida_falsa([(160, 160, 40, 120, 0.9)])
        r = decodificar(s, 0.25, 0, 70, 1280, 720)
        self.assertEqual(len(r), 1)
        x0, y0, x1, y1, nota = r[0]
        self.assertAlmostEqual((x0 + x1) / 2, 0.5, places=2)
        self.assertAlmostEqual((y0 + y1) / 2, 0.5, places=2)
        self.assertAlmostEqual(x1 - x0, 40 / 0.25 / 1280, places=3)
        self.assertAlmostEqual(nota, 0.9, places=3)

    def test_ignora_nota_baixa(self):
        s = self.saida_falsa([(160, 160, 40, 120, 0.05)])
        self.assertEqual(decodificar(s, 0.25, 0, 70, 1280, 720), [])

    def test_caixas_repetidas_viram_uma(self):
        s = self.saida_falsa([(160, 160, 40, 120, 0.9),
                              (162, 160, 40, 120, 0.8)])
        self.assertEqual(len(decodificar(s, 0.25, 0, 70, 1280, 720)), 1)

    def test_duas_pessoas_separadas(self):
        s = self.saida_falsa([(80, 160, 40, 120, 0.9),
                              (240, 160, 40, 120, 0.8)])
        self.assertEqual(len(decodificar(s, 0.25, 0, 70, 1280, 720)), 2)

    def test_aceita_matriz_transposta_e_com_lote(self):
        s = self.saida_falsa([(160, 160, 40, 120, 0.9)])
        self.assertEqual(len(decodificar(s.T, 0.25, 0, 70, 1280, 720)), 1)
        self.assertEqual(len(decodificar(s[None], 0.25, 0, 70, 1280, 720)), 1)

    def test_recorta_o_que_passa_da_borda(self):
        s = self.saida_falsa([(160, 300, 60, 160, 0.9)])    # passa de baixo
        x0, y0, x1, y1, _ = decodificar(s, 0.25, 0, 70, 1280, 720)[0]
        self.assertLessEqual(y1, 1.0)
        self.assertGreaterEqual(y0, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
