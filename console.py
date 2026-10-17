"""Console: a tela do monitor touch de 8" (1280x800).

Mostra só o que se opera com o dedo: botão de cadastrar, ajuste da linha de
contagem, zerar, sair, o aviso de privacidade e o teclado virtual. O painel
bonito para o público fica na TV (painel.py).

Qualidade: a parte fixa da tela (botões, cartões, textos) é desenhada com o
Pillow em dobro da resolução e reduzida (bordas suaves e cantos
arredondados) e fica guardada em cache; a cada quadro só se cola a prévia da
câmera e a barra de progresso. Assim fica bonito e leve.

desenhar(vm, agora)  ->  imagem BGR 1280x800
tocar(x, y, estado, agora) -> ação ("cadastrar", "aceitar", "cancelar",
    "linha_cima", "linha_baixo", "inverter", "zerar", "sair") ou None.
Zerar e sair pedem um segundo toque (em até 3 s) para evitar acidentes.
"""
import cv2
import numpy as np
from PIL import Image, ImageDraw

from fluxo import AVISO, CALIBRAR, ESPERA, FIM, NOME, POSES_, ROTULOS
from painel import _fonte
from texto_pil import texto

LARG, ALT = 1280, 800
S = 2                                     # supersampling do desenho fixo

# cores (RGB), as mesmas da TV
FUNDO = (11, 18, 32)
CARTAO = (20, 30, 51)
BORDA = (42, 58, 92)
TEXTO = (229, 231, 235)
SUAVE = (148, 163, 184)
CIANO = (34, 211, 238)
VERDE_T = (52, 211, 153)
AMARELO = (251, 191, 36)
BTN_VERDE = (22, 140, 96)
BTN_AZUL = (37, 88, 150)
BTN_VERM = (176, 52, 66)
BTN_CINZA = (51, 65, 88)
BTN_AMARELO = (251, 191, 36)

# áreas (x0, y0, x1, y1)
PREVIA = (30, 96, 790, 524)              # 760x428
B_CADASTRAR = (820, 96, 1250, 246)
B_LINHA_CIMA = (820, 266, 1025, 356)
B_LINHA_BAIXO = (1045, 266, 1250, 356)
B_INVERTER = (820, 376, 1250, 466)
B_ZERAR = (820, 486, 1025, 576)
B_SAIR = (1045, 486, 1250, 576)
CARTOES = [(30, 548, 205, 668), (225, 548, 400, 668),
           (420, 548, 595, 668), (615, 548, 790, 668)]
B_ACEITO = (60, 580, 620, 720)
B_RECUSA = (660, 580, 1220, 720)
B_CANCELAR = (860, 710, 1250, 780)
PREVIA_POSES = (40, 220, 760, 625)       # 720x405 (16:9, cabe com a barra)
BARRA = (40, 660, 1240, 690)

PRECISA_CONFIRMAR = {"zerar", "sair"}
CONFIRMAR_S = 3.0
RAIO_PREVIA = 20


def _dentro(r, x, y):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def _misturar(cor, com, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(cor, com))


class _Quadro:
    """Pequeno ajudante: desenha em dobro da resolução usando coordenadas
    normais (1280x800)."""

    def __init__(self):
        self.img = Image.new("RGB", (LARG * S, ALT * S), FUNDO)
        self.d = ImageDraw.Draw(self.img)

    def _r(self, ret):
        return tuple(int(v * S) for v in ret)

    def cartao(self, ret, raio=22, preenchimento=CARTAO, borda=BORDA):
        self.d.rounded_rectangle(self._r(ret), radius=raio * S,
                                 fill=preenchimento, outline=borda,
                                 width=2 * S)

    def botao(self, ret, rotulo, cor, tamanho=36, sub=None, cor_texto=TEXTO):
        x0, y0, x1, y1 = ret
        self.d.rounded_rectangle(self._r(ret), radius=24 * S, fill=cor,
                                 outline=_misturar(cor, (255, 255, 255), .35),
                                 width=2 * S)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if sub:
            self.t((cx, cy - tamanho * .18), rotulo, tamanho, cor_texto, "mm")
            self.t((cx, cy + tamanho * .62), sub, max(tamanho * .48, 20),
                   _misturar(cor_texto, cor, .25), "mm", False)
        else:
            self.t((cx, cy), rotulo, tamanho, cor_texto, "mm")

    def t(self, pos, txt, tamanho, cor=TEXTO, ancora="la", negrito=True):
        self.d.text((pos[0] * S, pos[1] * S), txt,
                    font=_fonte(int(tamanho * S), negrito), fill=cor,
                    anchor=ancora)

    def finalizar(self):
        pequena = self.img.resize((LARG, ALT), Image.LANCZOS)
        return np.asarray(pequena)[:, :, ::-1].copy()          # RGB -> BGR


class Console:
    def __init__(self):
        self._pendente = None            # (ação, até quando)
        self._cache_chave = None
        self._cache_img = None
        self._mascaras = {}

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

    def _acao_pendente(self, agora):
        if self._pendente and agora < self._pendente[1]:
            return self._pendente[0]
        return None

    # ---------- parte fixa (em cache) ----------
    def _base(self, vm, agora):
        estado = vm.get("estado", ESPERA)
        linha = vm.get("linha")
        linha_pct = int(round(linha[0][1] * 100)) if linha else 0
        chave = (estado, vm.get("titulo"), vm.get("subtitulo"),
                 vm.get("aviso"), self._acao_pendente(agora),
                 vm.get("dentro"), vm.get("entraram"), vm.get("sairam"),
                 vm.get("cadastradas"), tuple(vm.get("poses_feitas", ())),
                 vm.get("pose_atual"), linha_pct, vm.get("inverter"))
        if chave != self._cache_chave:
            q = _Quadro()
            if estado == ESPERA:
                self._fixo_espera(q, vm, agora, linha_pct)
            elif estado == AVISO:
                self._fixo_aviso(q)
            elif estado in (CALIBRAR, POSES_):
                self._fixo_poses(q, vm)
            elif estado == FIM:
                q.t((LARG / 2, 330), "Cadastrado!", 96, VERDE_T, "mm")
                q.t((LARG / 2, 450), vm.get("subtitulo", ""), 60, TEXTO, "mm")
            self._cache_img, self._cache_chave = q.finalizar(), chave
        return self._cache_img

    def _fixo_espera(self, q, vm, agora, linha_pct):
        q.t((30, 16), "Painel de controle", 36, TEXTO)
        q.t((31, 62), "o público vê o painel na TV", 20, SUAVE, "la", False)
        # selo "contando"
        q.cartao((1040, 34, 1250, 80), raio=23)
        q.d.ellipse(tuple(int(v * S) for v in (1062, 49, 1078, 65)),
                    fill=VERDE_T)
        q.t((1092, 57), "Contando", 24, TEXTO, "lm")
        # moldura da prévia
        q.cartao((PREVIA[0] - 4, PREVIA[1] - 4, PREVIA[2] + 4, PREVIA[3] + 4),
                 raio=RAIO_PREVIA + 4)
        # botões
        q.botao(B_CADASTRAR, "CADASTRAR", BTN_VERDE, 48,
                "ou mostre a mão aberta")
        q.botao(B_LINHA_CIMA, "LINHA  ▲", BTN_AZUL, 32)
        q.botao(B_LINHA_BAIXO, "LINHA  ▼", BTN_AZUL, 32)
        q.botao(B_INVERTER, "INVERTER SENTIDO", BTN_AZUL, 32,
                "troca o que conta como entrada")
        pend = self._acao_pendente(agora)
        for ret, acao, nome, cor in ((B_ZERAR, "zerar", "ZERAR", BTN_VERM),
                                     (B_SAIR, "sair", "SAIR", BTN_CINZA)):
            if pend == acao:
                q.botao(ret, "TOQUE DE NOVO", BTN_AMARELO, 26,
                        cor_texto=(30, 30, 30))
            else:
                q.botao(ret, nome, cor, 32,
                        "a contagem" if acao == "zerar" else None)
        # números
        dados = [("Dentro agora", vm.get("dentro", 0), CIANO),
                 ("Entraram", vm.get("entraram", 0), VERDE_T),
                 ("Saíram", vm.get("sairam", 0), TEXTO),
                 ("Cadastradas", vm.get("cadastradas", 0), AMARELO)]
        for ret, (rot, val, cor) in zip(CARTOES, dados):
            q.cartao(ret, raio=20)
            q.t((ret[0] + 18, ret[1] + 16), rot, 21, SUAVE, "la", False)
            q.t(((ret[0] + ret[2]) / 2, ret[1] + 82), str(val), 58, cor, "mm")
        # rodapé: aviso ou dica
        q.cartao((820, 596, 1250, 668), raio=20)
        q.t((842, 632), f"Linha de contagem a {linha_pct}% da altura", 22,
            SUAVE, "lm", False)
        aviso = vm.get("aviso")
        if aviso:
            q.cartao((30, 700, 1250, 770), raio=22, borda=AMARELO)
            q.t((LARG / 2, 735), aviso, 30, AMARELO, "mm")
        else:
            q.t((30, 735),
                "Guardamos só números do rosto, nunca fotos. "
                "Quem se cadastra pode pedir para apagar quando quiser.",
                22, SUAVE, "lm", False)

    def _fixo_aviso(self, q):
        q.t((LARG / 2, 110), "Aviso de privacidade", 62, CIANO, "mm")
        linhas = ["Vamos guardar apenas NÚMEROS do seu rosto",
                  "(nunca as fotos), junto com o seu nome,",
                  "para reconhecer você aqui.",
                  "Você pode pedir para apagar o cadastro quando quiser."]
        for i, l in enumerate(linhas):
            q.t((LARG / 2, 230 + i * 70), l, 38, TEXTO, "mm", False)
        q.botao(B_ACEITO, "ACEITO", BTN_VERDE, 56)
        q.botao(B_RECUSA, "CANCELAR", BTN_VERM, 56)

    def _fixo_poses(self, q, vm):
        q.t((LARG / 2, 80), vm.get("titulo", ""), 50, CIANO, "mm")
        q.t((LARG / 2, 150), vm.get("subtitulo", ""), 28, TEXTO, "mm", False)
        x0, y0, x1, y1 = PREVIA_POSES
        q.cartao((x0 - 4, y0 - 4, x1 + 4, y1 + 4), raio=RAIO_PREVIA + 4)
        feitas = vm.get("poses_feitas", ())
        atual = vm.get("pose_atual")
        for i, nome in enumerate(ROTULOS):
            feito, ativo = nome in feitas, nome == atual
            cor = VERDE_T if feito else (CIANO if ativo else SUAVE)
            marca = "✔" if feito else ("●" if ativo else "○")
            q.t((810, 250 + i * 70), f"{marca}  {ROTULOS[nome].title()}", 36,
                cor)
        bx0, by0, bx1, by1 = BARRA
        q.d.rounded_rectangle(tuple(int(v * S) for v in BARRA),
                              radius=((by1 - by0) // 2) * S, fill=CARTAO,
                              outline=BORDA, width=2 * S)
        if vm.get("aviso"):
            q.t((40, 735), vm["aviso"], 28, AMARELO, "lm")
        q.botao(B_CANCELAR, "CANCELAR", BTN_VERM, 32)

    # ---------- parte que muda a cada quadro ----------
    def _mascara_cantos(self, w, h, raio):
        chave = (w, h, raio)
        if chave not in self._mascaras:
            m = Image.new("L", (w * 4, h * 4), 0)
            ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 4 - 1, h * 4 - 1),
                                                radius=raio * 4, fill=255)
            self._mascaras[chave] = np.asarray(
                m.resize((w, h), Image.LANCZOS)).astype(np.float32) / 255.0
        return self._mascaras[chave]

    def _colar_camera(self, img, ret, vm, mostrar_linha):
        """Cola a câmera (com cantos arredondados) e as marcações."""
        x0, y0, x1, y1 = ret
        w, h = x1 - x0, y1 - y0
        cam = vm.get("camera")
        if cam is None:
            return
        cam = cv2.resize(cam, (w, h), interpolation=cv2.INTER_LINEAR)
        for p in vm.get("pessoas", ()):
            a, b, c, d = p["caixa"]
            cor = tuple(p.get("cor", CIANO))[::-1]
            cv2.rectangle(cam, (int(a * w), int(b * h)),
                          (int(c * w), int(d * h)), cor, 2, cv2.LINE_AA)
        linha = vm.get("linha")
        if mostrar_linha and linha:
            (ax, ay), (bx, by) = linha
            p = (int(ax * w), int(ay * h))
            q = (int(bx * w), int(by * h))
            cv2.line(cam, p, q, (0, 215, 255), 3, cv2.LINE_AA)
            sentido = -1 if vm.get("inverter") else 1
            mx, my = (p[0] + q[0]) // 2, (p[1] + q[1]) // 2
            cv2.arrowedLine(cam, (mx, my - 34 * sentido),
                            (mx, my + 34 * sentido), (0, 215, 255), 5,
                            cv2.LINE_AA, tipLength=0.4)
            texto(cam, "ENTRADA", (mx + 18, my + 44 * sentido), 24,
                  (0, 215, 255), "lm")
        # cantos arredondados: mistura só a região dos cantos
        roi = img[y0:y1, x0:x1]
        m = self._mascara_cantos(w, h, RAIO_PREVIA)
        r = RAIO_PREVIA + 1
        for ys, xs in ((slice(0, r), slice(0, r)), (slice(0, r), slice(w - r, w)),
                       (slice(h - r, h), slice(0, r)),
                       (slice(h - r, h), slice(w - r, w))):
            alfa = m[ys, xs][..., None]
            cam[ys, xs] = (cam[ys, xs] * alfa +
                           roi[ys, xs] * (1 - alfa)).astype(np.uint8)
        roi[:] = cam

    def desenhar(self, vm, agora, teclado=None, mostrar_linha=False):
        """vm: 'estado', 'titulo', 'subtitulo', 'progresso', 'aviso',
        'camera' (BGR), 'pessoas', 'linha', 'inverter', 'dentro',
        'entraram', 'sairam', 'cadastradas', 'poses_feitas', 'pose_atual'.
        mostrar_linha: mostra a linha de contagem e a seta de ENTRADA na
        prévia (só enquanto se ajusta; o resto do tempo fica limpo)."""
        estado = vm.get("estado", ESPERA)
        if estado == NOME and teclado is not None:
            img = np.full((ALT, LARG, 3), FUNDO[::-1], np.uint8)
            teclado.desenhar(img, "DIGITE O NOME E TOQUE EM OK")
            if vm.get("aviso"):
                texto(img, vm["aviso"], (LARG - 40, 60), 34, AMARELO[::-1],
                      "rm")
            return img

        img = self._base(vm, agora).copy()
        if estado == ESPERA:
            self._colar_camera(img, PREVIA, vm, mostrar_linha)
        elif estado in (CALIBRAR, POSES_):
            self._colar_camera(img, PREVIA_POSES, vm, False)
            p = min(max(vm.get("progresso", 0.0), 0.0), 1.0)
            bx0, by0, bx1, by1 = BARRA
            if p > 0:
                cy, esp = (by0 + by1) // 2, by1 - by0 - 8
                xa, xb = bx0 + 4 + esp // 2, bx0 + 4 + esp // 2 + \
                    int((bx1 - bx0 - 8 - esp) * p)
                cor = CIANO[::-1]
                cv2.line(img, (xa, cy), (xb, cy), cor, esp, cv2.LINE_AA)
                for xc in (xa, xb):
                    cv2.circle(img, (xc, cy), esp // 2, cor, -1, cv2.LINE_AA)
        return img
