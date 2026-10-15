"""Testes da lógica de poses (não precisam de câmera nem de MediaPipe).

Rodar:  python test_poses.py
"""
import unittest

import poses
from poses import (CalibradorDeFrente, GuiaDePoses, classificar_pose,
                   razoes_da_cabeca)


def rosto_falso(nariz_x=0.5, nariz_y=0.6, invertido=False):
    """Malha de 478 pontos onde só os pontos usados têm valor útil.
    Rosto de x=0.3 a x=0.7 e de y=0.2 (testa) a y=0.8 (queixo)."""
    pontos = [(0.5, 0.5)] * 478
    pontos = list(pontos)
    a, b = (0.3, 0.7) if not invertido else (0.7, 0.3)
    pontos[poses.BOCHECHA_A] = (a, 0.5)
    pontos[poses.BOCHECHA_B] = (b, 0.5)
    pontos[poses.TESTA] = (0.5, 0.2)
    pontos[poses.QUEIXO] = (0.5, 0.8)
    pontos[poses.PONTA_DO_NARIZ] = (nariz_x, nariz_y)
    return pontos


class TesteRazoes(unittest.TestCase):
    def test_de_frente(self):
        yaw, pitch = razoes_da_cabeca(rosto_falso(0.5, 0.56))
        self.assertAlmostEqual(yaw, 0.5)
        self.assertAlmostEqual(pitch, 0.6)

    def test_nariz_para_direita_aumenta_yaw(self):
        yaw, _ = razoes_da_cabeca(rosto_falso(0.6, 0.56))
        self.assertGreater(yaw, 0.5)

    def test_funciona_com_imagem_espelhada(self):
        # com a imagem espelhada, as bochechas trocam de lado, mas "direita"
        # continua sendo a direita da imagem
        yaw_normal, _ = razoes_da_cabeca(rosto_falso(0.6, 0.56))
        yaw_espelho, _ = razoes_da_cabeca(rosto_falso(0.6, 0.56,
                                                      invertido=True))
        self.assertAlmostEqual(yaw_normal, yaw_espelho)

    def test_sem_pontos(self):
        self.assertIsNone(razoes_da_cabeca(None))
        self.assertIsNone(razoes_da_cabeca([]))
        self.assertIsNone(razoes_da_cabeca([(0.5, 0.5)] * 10))


class TesteClassificar(unittest.TestCase):
    def test_centro(self):
        self.assertEqual(classificar_pose(0.5, 0.6), "centro")

    def test_esquerda_e_direita(self):
        self.assertEqual(classificar_pose(0.35, 0.6), "esquerda")
        self.assertEqual(classificar_pose(0.65, 0.6), "direita")

    def test_cima_e_baixo(self):
        # olhar para cima faz o nariz subir -> pitch diminui
        self.assertEqual(classificar_pose(0.5, 0.5), "cima")
        self.assertEqual(classificar_pose(0.5, 0.7), "baixo")

    def test_usa_a_linha_de_base(self):
        # para quem tem base 0.45, o valor 0.45 é "centro"
        self.assertEqual(classificar_pose(0.45, 0.6, base_yaw=0.45), "centro")
        self.assertEqual(classificar_pose(0.5, 0.6, base_yaw=0.45), "centro")
        self.assertEqual(classificar_pose(0.62, 0.6, base_yaw=0.45), "direita")

    def test_sem_rosto(self):
        self.assertIsNone(classificar_pose(None, None))

    def test_ganha_o_movimento_dominante(self):
        # muito para a direita e só um pouco para cima
        self.assertEqual(classificar_pose(0.7, 0.56), "direita")


class TesteCalibrador(unittest.TestCase):
    def test_media_das_amostras(self):
        c = CalibradorDeFrente(amostras=4)
        for yaw, pitch in [(0.4, 0.5), (0.5, 0.6), (0.5, 0.6), (0.6, 0.7)]:
            c.adicionar(yaw, pitch)
        self.assertTrue(c.pronto)
        self.assertAlmostEqual(c.base_yaw, 0.5)
        self.assertAlmostEqual(c.base_pitch, 0.6)

    def test_ignora_quadros_sem_rosto(self):
        c = CalibradorDeFrente(amostras=2)
        c.adicionar(None, None)
        self.assertEqual(c.progresso, 0.0)
        c.adicionar(0.5, 0.6)
        self.assertEqual(c.progresso, 0.5)


class TesteGuia(unittest.TestCase):
    def novo(self):
        return GuiaDePoses(passos=("centro", "esquerda"), segurar_s=1.0,
                           pausa_s=0.5, tolerancia_s=0.2)

    def test_confirma_apos_segurar(self):
        g = self.novo()
        self.assertEqual(g.update("centro", 0.0), (0.0, False))
        p, ok = g.update("centro", 0.5)
        self.assertAlmostEqual(p, 0.5)
        self.assertFalse(ok)
        p, ok = g.update("centro", 1.0)
        self.assertEqual((p, ok), (1.0, True))
        self.assertEqual(g.passo_atual, "esquerda")

    def test_pose_errada_nao_avanca(self):
        g = self.novo()
        for t in (0.0, 0.5, 1.0, 1.5, 2.0):
            _, ok = g.update("direita", t)
            self.assertFalse(ok)
        self.assertEqual(g.indice, 0)

    def test_pausa_depois_de_confirmar(self):
        g = self.novo()
        g.update("centro", 0.0)
        g.update("centro", 1.0)  # confirma o passo 1
        # durante a pausa nada conta, mesmo na pose certa do próximo passo
        self.assertEqual(g.update("esquerda", 1.2), (0.0, False))
        self.assertEqual(g.update("esquerda", 1.4), (0.0, False))
        g.update("esquerda", 1.6)          # pausa acabou, começa a contar
        p, ok = g.update("esquerda", 2.6)
        self.assertEqual((p, ok), (1.0, True))
        self.assertTrue(g.concluido)

    def test_perdoa_falha_curta(self):
        g = self.novo()
        g.update("centro", 0.0)
        g.update("centro", 0.4)
        g.update(None, 0.5)                # falha de 0,1 s: tolerada
        p, ok = g.update("centro", 0.6)
        self.assertFalse(ok)
        self.assertAlmostEqual(p, 0.6)

    def test_falha_longa_reinicia(self):
        g = self.novo()
        g.update("centro", 0.0)
        g.update("centro", 0.5)
        g.update("direita", 1.0)           # 0,5 s fora da pose: reinicia
        self.assertEqual(g.update("direita", 1.1), (0.0, False))
        g.update("centro", 1.2)
        p, ok = g.update("centro", 1.7)
        self.assertAlmostEqual(p, 0.5)
        self.assertFalse(ok)

    def test_nao_confirma_sem_a_pessoa_na_pose(self):
        g = self.novo()
        g.update("centro", 0.0)
        g.update("centro", 0.9)
        # a pessoa some e o relógio passa de 1 s, mas nada deve confirmar
        _, ok = g.update(None, 1.05)
        self.assertFalse(ok)

    def test_reiniciar(self):
        g = self.novo()
        g.update("centro", 0.0)
        g.update("centro", 1.0)
        g.reiniciar()
        self.assertEqual(g.passo_atual, "centro")
        self.assertFalse(g.concluido)


if __name__ == "__main__":
    unittest.main(verbosity=2)
