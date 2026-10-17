"""Teste de simulação do núcleo: pessoas, rosto, toque e teclado falsos,
com o painel e o console de verdade (sem câmera, sem modelos).

Rodar:  python test_nucleo.py
"""
import os
import tempfile
import unittest

import numpy as np

import console as con
from banco import Banco
from console import Console
from estatisticas import Configuracao, RegistroDeEventos
from fluxo import AVISO, ESPERA, NOME
from nucleo import Nucleo
from painel import Painel
from test_poses import rosto_falso

FRAME = np.full((720, 1280, 3), 40, np.uint8)
VETOR = np.random.RandomState(1).randn(128).astype(np.float32)
VETOR /= np.linalg.norm(VETOR)
NARIZ = {"centro": (0.5, 0.56), "esquerda": (0.35, 0.56),
         "direita": (0.65, 0.56), "cima": (0.5, 0.45), "baixo": (0.5, 0.68)}


def centro(r):
    return (r[0] + r[2]) // 2, (r[1] + r[3]) // 2


class RostoFalso:
    def __init__(self):
        self.malhas = []

    def detectar_todos(self, frame):
        return self.malhas


class GestosFalso:
    def __init__(self):
        self.gesto = None

    def detectar(self, frame):
        return (self.gesto, 0.9)


class TesteNucleo(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        p = self.pasta.name
        self.banco = Banco(os.path.join(p, "t.db"))
        self.config = Configuracao(os.path.join(p, "config.json"))
        self.rosto, self.gestos = RostoFalso(), GestosFalso()
        self.extraido = VETOR
        self.nucleo = Nucleo(
            self.banco, lambda f, pts: self.extraido, self.rosto, self.gestos,
            Painel(), Console(), self.config,
            RegistroDeEventos(os.path.join(p, "ev.csv")))
        self.t = 1000.0

    def tearDown(self):
        self.banco.fechar()
        self.pasta.cleanup()

    def passo(self, y=None, toque=None, tecla=None, dt=0.05):
        det = None
        if y is not None:
            det = [(0.3, max(y - 0.6, 0.0), 0.7, y, 0.9)] if y >= 0 else []
        self.t += dt
        return self.nucleo.passo(FRAME, self.t, det, toque, tecla)

    def andar(self, y0, y1, passos=20):
        for i in range(passos + 1):
            self.passo(y0 + (y1 - y0) * i / passos)

    def test_telas_tem_o_tamanho_certo(self):
        tv, touch = self.passo(None)
        self.assertEqual(tv.shape, (1080, 1920, 3))
        self.assertEqual(touch.shape, (800, 1280, 3))

    def test_conta_entrada_e_saida(self):
        self.andar(0.35, 0.8)           # pés de cima para baixo: entra
        self.assertEqual(self.nucleo.contador.entraram, 1)
        self.passo(-1)
        self.t += 3
        self.passo(-1)
        self.andar(0.8, 0.62)           # pessoa nova (outro ID) aparece embaixo
        self.assertEqual(self.nucleo.contador.entraram, 1)
        self.assertEqual(self.nucleo.contador.sairam, 0)  # só aparece do lado de dentro

    def test_saida_conta_ao_cruzar_para_cima(self):
        self.andar(0.8, 0.35)
        self.assertEqual(self.nucleo.contador.sairam, 1)

    def test_grava_evento_no_csv(self):
        self.andar(0.35, 0.8)
        caminho = self.nucleo.registro.caminho
        self.assertIn(",entrou,", open(caminho, encoding="utf-8").read())

    def test_reconhece_quem_esta_cadastrado(self):
        self.banco.cadastrar("Ana", {"centro": VETOR})
        self.rosto.malhas = [rosto_falso(*NARIZ["centro"])]
        for _ in range(60):
            self.passo(0.8)
        self.assertEqual(self.nucleo.identidades.nome(1), "Ana")

    def test_desconhecido_fica_sem_nome(self):
        outro = np.random.RandomState(7).randn(128).astype(np.float32)
        self.extraido = outro / np.linalg.norm(outro)
        self.banco.cadastrar("Ana", {"centro": VETOR})
        self.rosto.malhas = [rosto_falso(*NARIZ["centro"])]
        for _ in range(60):
            self.passo(0.8)
        self.assertIsNone(self.nucleo.identidades.nome(1))
        self.assertEqual(self.nucleo.identidades.rotulo(1), "Pessoa · ID 1")

    def test_cadastro_pelo_toque_ate_o_fim(self):
        self.rosto.malhas = [rosto_falso(*NARIZ["centro"])]
        self.passo(0.8)
        self.passo(0.8, toque=centro(con.B_CADASTRAR))
        self.assertEqual(self.nucleo.fluxo.estado, AVISO)
        self.passo(0.8, toque=centro(con.B_ACEITO))
        for _ in range(100):                           # calibra
            self.passo(0.8)
        for pose in ("centro", "esquerda", "direita", "cima", "baixo"):
            self.rosto.malhas = [rosto_falso(*NARIZ[pose])]
            for _ in range(40):
                self.passo(0.8)
        self.assertEqual(self.nucleo.fluxo.estado, NOME)
        for ch in "Léo":
            if ord(ch) < 128:
                self.passo(0.8, tecla=ord(ch))
        self.passo(0.8, tecla=13)
        self.assertTrue(self.banco.existe_nome("Leo") or
                        self.banco.existe_nome("Lo"))
        for _ in range(80):
            self.passo(0.8)
        self.assertEqual(self.nucleo.fluxo.estado, ESPERA)
        # quem acabou de se cadastrar já aparece com o nome
        self.assertIsNotNone(self.nucleo.identidades.nome(1))

    def test_gesto_inicia_o_cadastro(self):
        self.rosto.malhas = [rosto_falso(*NARIZ["centro"])]
        self.gestos.gesto = "Open_Palm"
        for _ in range(40):
            self.passo(0.8)
        self.assertEqual(self.nucleo.fluxo.estado, AVISO)

    def test_linha_sobe_desce_e_salva(self):
        antes = self.nucleo.linha_y
        self.passo(None, toque=centro(con.B_LINHA_CIMA))
        self.assertAlmostEqual(self.nucleo.linha_y, antes - 0.02)
        self.passo(None, toque=centro(con.B_LINHA_BAIXO))
        self.passo(None, toque=centro(con.B_LINHA_BAIXO))
        self.assertAlmostEqual(self.nucleo.linha_y, antes + 0.02)
        self.assertAlmostEqual(
            Configuracao(self.config.caminho).obter("linha_y"), antes + 0.02)

    def test_inverter_troca_o_sentido(self):
        self.passo(None, toque=centro(con.B_INVERTER))
        self.assertTrue(self.nucleo.inverter)
        self.andar(0.35, 0.8)
        self.assertEqual(self.nucleo.contador.sairam, 1)   # agora é saída

    def test_zerar_pede_confirmacao(self):
        self.andar(0.35, 0.8)
        self.passo(None, toque=centro(con.B_ZERAR))
        self.assertEqual(self.nucleo.contador.entraram, 1)
        self.passo(None, toque=centro(con.B_ZERAR))
        self.assertEqual(self.nucleo.contador.entraram, 0)

    def test_sair_pede_confirmacao(self):
        self.passo(None, toque=centro(con.B_SAIR))
        self.assertFalse(self.nucleo.sair)
        self.passo(None, toque=centro(con.B_SAIR))
        self.assertTrue(self.nucleo.sair)

    def test_tecla_q_sai_so_na_espera(self):
        self.passo(None, tecla=ord("q"))
        self.assertTrue(self.nucleo.sair)

    def test_linha_so_aparece_ao_ajustar(self):
        self.rosto.malhas = []
        self.passo(None)
        self.assertEqual(self.nucleo._guia_ate < self.t, True)
        self.passo(None, toque=centro(con.B_LINHA_CIMA))
        self.assertGreater(self.nucleo._guia_ate, self.t)

    def test_console_usa_cache_da_parte_fixa(self):
        c = self.nucleo.console
        self.passo(None)
        antes = c._cache_img
        self.passo(None)
        self.t += 1
        self.passo(None)
        self.assertIs(c._cache_img, antes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
