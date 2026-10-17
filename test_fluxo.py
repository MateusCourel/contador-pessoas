"""Testes do fluxo de cadastro (sem câmera, sem modelos).

Rodar:  python test_fluxo.py
"""
import os
import tempfile
import unittest

import numpy as np

from banco import Banco
from fluxo import (AVISO, CALIBRAR, ESPERA, FIM, NOME, POSES_,
                   FluxoDeCadastro, largura_do_rosto)
from test_poses import rosto_falso

FRAME = np.zeros((720, 1280, 3), np.uint8)
# posição do nariz que produz cada pose (rosto_falso: de frente = 0.5/0.56)
NARIZ = {"centro": (0.5, 0.56), "esquerda": (0.35, 0.56),
         "direita": (0.65, 0.56), "cima": (0.5, 0.45), "baixo": (0.5, 0.68)}


def emb_falso(frame, pontos):
    v = np.random.rand(128).astype(np.float32)
    return v / np.linalg.norm(v)


class Base(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = Banco(os.path.join(self.pasta.name, "t.db"))
        self.fluxo = FluxoDeCadastro(self.banco, emb_falso, fim_s=2.0)
        self.t = 100.0

    def tearDown(self):
        self.banco.fechar()
        self.pasta.cleanup()

    def rodar(self, pontos, segundos, dt=0.05):
        fim = self.t + segundos
        while self.t < fim:
            self.fluxo.passo(FRAME, pontos, self.t)
            self.t += dt

    def ate_calibrar(self):
        self.fluxo.iniciar(self.t)
        self.fluxo.aceitar(self.t)

    def ate_nome(self):
        self.ate_calibrar()
        self.rodar(rosto_falso(*NARIZ["centro"]), 4.0)
        self.assertEqual(self.fluxo.estado, POSES_)
        for pose in ("centro", "esquerda", "direita", "cima", "baixo"):
            self.rodar(rosto_falso(*NARIZ[pose]), 2.0)
        self.assertEqual(self.fluxo.estado, NOME)


class TesteFluxo(Base):
    def test_comeca_parado(self):
        self.assertEqual(self.fluxo.estado, ESPERA)
        self.assertFalse(self.fluxo.ativo)

    def test_iniciar_vai_para_aviso(self):
        self.assertTrue(self.fluxo.iniciar(self.t))
        self.assertEqual(self.fluxo.estado, AVISO)
        self.assertFalse(self.fluxo.iniciar(self.t))      # já em andamento

    def test_aceitar_vai_para_calibrar_e_cancelar_volta(self):
        self.ate_calibrar()
        self.assertEqual(self.fluxo.estado, CALIBRAR)
        self.fluxo.cancelar(agora=self.t)
        self.assertEqual(self.fluxo.estado, ESPERA)
        self.assertEqual(self.fluxo.aviso(self.t), "CADASTRO CANCELADO")

    def test_aviso_parado_expira(self):
        self.fluxo.iniciar(self.t)
        self.rodar(None, 46)
        self.assertEqual(self.fluxo.estado, ESPERA)
        self.assertEqual(self.fluxo.aviso(self.t), "TEMPO ESGOTADO")

    def test_sem_rosto_expira(self):
        self.ate_calibrar()
        self.rodar(None, 5)
        self.assertEqual(self.fluxo.estado, CALIBRAR)
        self.assertIn("nenhum rosto", self.fluxo.subtitulo)
        self.rodar(None, 20)
        self.assertEqual(self.fluxo.estado, ESPERA)

    def test_cadastro_completo(self):
        self.ate_nome()
        for ch in "Ana":
            self.fluxo.tecla_fisica(ord(ch), self.t)
        self.fluxo.tecla_fisica(13, self.t)
        self.assertEqual(self.fluxo.estado, FIM)
        self.assertEqual(self.fluxo.pop_cadastrado(), "Ana")
        self.assertIsNone(self.fluxo.pop_cadastrado())
        self.assertTrue(self.banco.existe_nome("Ana"))
        self.rodar(None, 2.5)
        self.assertEqual(self.fluxo.estado, ESPERA)

    def test_cinco_poses_gravadas(self):
        self.ate_nome()
        self.assertEqual(len(self.fluxo.poses_feitas), 5)

    def test_nome_vazio_e_repetido(self):
        self.ate_nome()
        self.fluxo.tecla_fisica(13, self.t)
        self.assertEqual(self.fluxo.aviso(self.t), "DIGITE UM NOME")
        self.assertEqual(self.fluxo.estado, NOME)
        self.banco.cadastrar("Ana", {"centro": emb_falso(None, None)})
        for ch in "Ana":
            self.fluxo.tecla_fisica(ord(ch), self.t)
        self.fluxo.tecla_fisica(13, self.t)
        self.assertEqual(self.fluxo.aviso(self.t), "JÁ EXISTE ESSE NOME")
        self.assertEqual(self.fluxo.estado, NOME)

    def test_cancelar_pelo_teclado_virtual(self):
        self.ate_nome()
        self.fluxo._tratar_acao("cancelar", self.t)
        self.assertEqual(self.fluxo.estado, ESPERA)
        self.assertEqual(self.banco.listar(), [])

    def test_rosto_pequeno_refaz_a_pose(self):
        self.fluxo.extrair = lambda f, p: None             # extração falha
        self.ate_calibrar()
        self.rodar(rosto_falso(*NARIZ["centro"]), 4.0)
        self.rodar(rosto_falso(*NARIZ["centro"]), 2.0)
        self.assertEqual(self.fluxo.estado, POSES_)
        self.assertEqual(self.fluxo.pose_atual, "centro")  # não avançou
        self.assertEqual(self.fluxo.poses_feitas, [])

    def test_tempo_do_nome_expira(self):
        self.ate_nome()
        self.rodar(None, 95)
        self.assertEqual(self.fluxo.estado, ESPERA)

    def test_textos_de_cada_etapa(self):
        self.fluxo.iniciar(self.t)
        self.assertEqual(self.fluxo.titulo, "AVISO DE PRIVACIDADE")
        self.fluxo.aceitar(self.t)
        self.fluxo.passo(FRAME, rosto_falso(), self.t)
        self.assertIn("CÂMERA", self.fluxo.titulo)

    def test_largura(self):
        self.assertEqual(largura_do_rosto(rosto_falso(), 1000), 400)
        self.assertEqual(largura_do_rosto(None, 1000), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
