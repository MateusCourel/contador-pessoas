"""Console: a tela do monitor touch de 8" (1280x800).

Mostra só o que se opera com o dedo: botão de cadastrar, ajuste da linha de
contagem, zerar, sair, o aviso de privacidade e o teclado virtual. O painel
bonito para o público fica na TV (painel.py).

desenhar(vm, agora)  ->  imagem BGR 1280x800
tocar(x, y, estado, agora) -> ação ("cadastrar", "aceitar", "cancelar",
    "linha_cima", "linha_baixo", "inverter", "zerar", "sair") ou None.
Zerar e sair pedem um segundo toque (em até 3 s) para evitar acidentes.
"""
import cv2
import numpy as np

from fluxo import AVISO, CALIBRAR, ESPERA, FIM, NOME, POSES_, ROTULOS
from texto_pil import medir, texto

LARG, ALT = 1280, 800
FUNDO = (32, 18, 11)         # BGR
CARTAO = (51, 30, 20)
BRANCO = (235, 231, 229)
SUAVE = (184, 163, 148)
CIANO = (238, 211, 34)
VERDE = (60, 150, 60)
VERMELHO = (60, 60, 180)
AZUL = (150, 100, 50)
AMARELO = (36, 191, 251)
CINZA = (90, 70, 55)

PREVIA = (30, 110, 670, 470)         # x0, y0, x1, y1 (640x360)
B_CADASTRAR = (700, 110, 1250, 230)
B_LINHA_CIMA = (700, 250, 970, 340)
B_LINHA_BAIXO = (980, 250, 1250, 340)
B_INVERTER = (700, 360, 1250, 450)
B_ZERAR = (700, 470, 970, 560)
B_SAIR = (980, 470, 1250, 560)
B_ACEITO = (60, 600, 620, 740)
B_RECUSA = (660, 600, 1220, 740)
B_CANCELAR = (880, 700, 1250, 770)

PRECISA_CONFIRMAR = {"zerar", "sair"}
CONFIRMAR_S = 3.0


def _dentro(r, x, y):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


class Console:
    def __init__(self):
        self._pendente = None            # (ação, até quando)

    # ---------- toque ----------
    def _botoes(self, estado):
        if estado == ESPERA:
            return [("cadastrar", B_CADASTRAR), ("linha_cima", B_LINHA_CIMA),
                    ("linha_baixo", B_LINHA_BAIXO), ("inverter", B_INVERTER),
                    ("zerar", B_ZERAR), ("sair", B_SAIR)]
        if estado == AVISO:
            return [("aceitar", B_ACEITO), ("cancelar", B_RECUSA)]
        if estado in (CALIBRAR, POSES_):
            return [("cancelar", B_CANCELAR)]
        return []

    def tocar(self, x, y, estado, agora):
        for acao, ret in self._botoes(estado):
            if not _dentro(ret, x, y):
                continue
            if acao in PRECISA_CONFIRMAR:
                if self._pendente and self._pendente[0] == acao and \
                        agora < self._pendente[1]:
                    self._pendente = None
                    return acao
                self._pendente = (acao, agora + CONFIRMAR_S)
                return None
            self._pendente = None
            return acao
        return None

    # ---------- desenho ----------
    def _botao(self, img, ret, rotulo, cor, tamanho=40, sub=None):
        x0, y0, x1, y1 = ret
        cv2.rectangle(img, (x0, y0), (x1, y1), cor, -1)
        cv2.rectangle(img, (x0, y0), (x1, y1), BRANCO, 2)
        cy = (y0 + y1) // 2
        if sub:
            texto(img, rotulo, ((x0 + x1) // 2, cy - 14), tamanho, BRANCO,
                  "mm")
            texto(img, sub, ((x0 + x1) // 2, cy + 22), 22, BRANCO, "mm",
                  negrito=False)
        else:
            texto(img, rotulo, ((x0 + x1) // 2, cy), tamanho, BRANCO, "mm")

    def _previa(self, img, vm):
        x0, y0, x1, y1 = PREVIA
        cam = vm.get("camera")
        w, h = x1 - x0, y1 - y0
        if cam is not None:
            img[y0:y1, x0:x1] = cv2.resize(cam, (w, h),
                                           interpolation=cv2.INTER_AREA)
        else:
            img[y0:y1, x0:x1] = CARTAO
        for p in vm.get("pessoas", ()):
            a, b, c, d = p["caixa"]
            cor = tuple(p.get("cor", (34, 211, 238)))[::-1]
            cv2.rectangle(img, (x0 + int(a * w), y0 + int(b * h)),
                          (x0 + int(c * w), y0 + int(d * h)), cor, 2)
        linha = vm.get("linha")
        if linha:
            (ax, ay), (bx, by) = linha
            p = (x0 + int(ax * w), y0 + int(ay * h))
            q = (x0 + int(bx * w), y0 + int(by * h))
            cv2.line(img, p, q, (0, 215, 255), 3, cv2.LINE_AA)
            # seta: sentido de ENTRADA (para baixo, ou para cima se invertido)
            sentido = -1 if vm.get("inverter") else 1
            mx, my = (p[0] + q[0]) // 2, (p[1] + q[1]) // 2
            cv2.arrowedLine(img, (mx, my - 30 * sentido),
                            (mx, my + 30 * sentido), (0, 215, 255), 4,
                            cv2.LINE_AA, tipLength=0.4)
            texto(img, "ENTRADA", (mx + 14, my + 38 * sentido), 22,
                  (0, 215, 255), "lm")
        cv2.rectangle(img, (x0, y0), (x1, y1), BRANCO, 2)

    def desenhar(self, vm, agora, teclado=None):
        """vm: dicionário com 'estado', 'titulo', 'subtitulo', 'progresso',
        'aviso', 'camera' (BGR), 'pessoas', 'linha', 'inverter', 'dentro',
        'entraram', 'sairam', 'cadastradas', 'poses_feitas', 'pose_atual'."""
        img = np.full((ALT, LARG, 3), FUNDO, np.uint8)
        estado = vm.get("estado", ESPERA)

        if estado == NOME and teclado is not None:
            teclado.desenhar(img, "DIGITE O NOME E TOQUE EM OK")
            if vm.get("aviso"):
                texto(img, vm["aviso"], (LARG - 40, 60), 34, AMARELO, "rm")
            return img

        if estado == ESPERA:
            self._tela_espera(img, vm, agora)
        elif estado == AVISO:
            self._tela_aviso(img, vm)
        elif estado in (CALIBRAR, POSES_):
            self._tela_poses(img, vm)
        elif estado == FIM:
            texto(img, "CADASTRADO!", (LARG // 2, 330), 90, (80, 220, 90),
                  "mm")
            texto(img, vm.get("subtitulo", ""), (LARG // 2, 450), 60, BRANCO,
                  "mm")
        return img

    def _tela_espera(self, img, vm, agora):
        texto(img, "PAINEL DE CONTROLE", (30, 25), 44, BRANCO)
        texto(img, "o público vê o painel na TV", (30, 78), 24, SUAVE,
              negrito=False)
        self._previa(img, vm)
        self._botao(img, B_CADASTRAR, "CADASTRAR", VERDE, 52,
                    "ou mostre a mão aberta para a câmera")
        self._botao(img, B_LINHA_CIMA, "LINHA  ▲", AZUL, 36)
        self._botao(img, B_LINHA_BAIXO, "LINHA  ▼", AZUL, 36)
        self._botao(img, B_INVERTER, "INVERTER SENTIDO", AZUL, 36,
                    "troca o que conta como entrada")
        for ret, acao, nome, cor in ((B_ZERAR, "zerar", "ZERAR CONTAGEM",
                                      VERMELHO),
                                     (B_SAIR, "sair", "SAIR", CINZA)):
            pend = self._pendente and self._pendente[0] == acao and \
                agora < self._pendente[1]
            self._botao(img, ret, "TOQUE DE NOVO" if pend else nome,
                        AMARELO if pend else cor, 30 if pend else 28)
        y = 500
        for rot, val in (("Dentro agora", vm.get("dentro", 0)),
                         ("Entraram", vm.get("entraram", 0)),
                         ("Saíram", vm.get("sairam", 0)),
                         ("Cadastradas", vm.get("cadastradas", 0))):
            texto(img, rot, (40, y), 28, SUAVE, negrito=False)
            texto(img, str(val), (330, y), 34, BRANCO, "ra")
            y += 48
        if vm.get("aviso"):
            texto(img, vm["aviso"], (LARG // 2, 770), 34, AMARELO, "mm")

    def _tela_aviso(self, img, vm):
        texto(img, "AVISO DE PRIVACIDADE", (LARG // 2, 100), 60, CIANO, "mm")
        linhas = ["Vamos guardar apenas NÚMEROS do seu rosto",
                  "(nunca as fotos), junto com o seu nome,",
                  "para reconhecer você aqui.",
                  "Você pode pedir para apagar o cadastro quando quiser."]
        for i, l in enumerate(linhas):
            texto(img, l, (LARG // 2, 220 + i * 70), 38, BRANCO, "mm",
                  negrito=False)
        self._botao(img, B_ACEITO, "ACEITO", VERDE, 56)
        self._botao(img, B_RECUSA, "CANCELAR", VERMELHO, 56)

    def _tela_poses(self, img, vm):
        texto(img, vm.get("titulo", ""), (LARG // 2, 100), 52, CIANO, "mm")
        texto(img, vm.get("subtitulo", ""), (LARG // 2, 170), 30, BRANCO,
              "mm", negrito=False)
        x0, y0, x1, y1 = 40, 230, 760, 590
        cam = vm.get("camera")
        if cam is not None:
            img[y0:y1, x0:x1] = cv2.resize(cam, (x1 - x0, y1 - y0),
                                           interpolation=cv2.INTER_AREA)
        cv2.rectangle(img, (x0, y0), (x1, y1), BRANCO, 2)
        feitas = vm.get("poses_feitas", ())
        atual = vm.get("pose_atual")
        for i, nome in enumerate(ROTULOS):
            feito, agora_ = nome in feitas, nome == atual
            cor = (90, 220, 90) if feito else (CIANO if agora_ else SUAVE)
            texto(img, ("✔ " if feito else "• ") + ROTULOS[nome],
                  (820, 250 + i * 60), 36, cor)
        p = min(max(vm.get("progresso", 0.0), 0.0), 1.0)
        cv2.rectangle(img, (40, 620), (1240, 650), BRANCO, 2)
        if p > 0:
            cv2.rectangle(img, (40, 620), (40 + int(1200 * p), 650), CIANO, -1)
        if vm.get("aviso"):
            texto(img, vm["aviso"], (40, 690), 30, AMARELO)
        self._botao(img, B_CANCELAR, "CANCELAR", VERMELHO, 34)
