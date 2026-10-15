"""Teclado virtual para a tela touch.

A lógica (o que cada toque faz) é separada do desenho, para poder ser testada
sem tela. Funcionalidades:
  - letras A-Z e Ç; a primeira letra de cada palavra sai maiúscula sozinha
  - SHIFT para uma letra maiúscula avulsa
  - acentos como "tecla morta": toque em ´ ` ^ ou ~ e depois na vogal
    (~ + a = ã, ´ + e = é, ^ + o = ô, ` + a = à)
  - APAGAR, ESPAÇO, OK e CANCELAR

As coordenadas são do "quadro lógico" (1280x720 por padrão). A janela pode
estar em tela cheia em qualquer resolução: o OpenCV ajusta o tamanho.
"""
import time
import unicodedata

import cv2
import numpy as np

ACENTOS = {"´": "́", "`": "̀", "^": "̂", "~": "̃"}

# Cada linha: (rótulo, ação, peso da largura)
LINHAS = [
    [(c, "letra", 1) for c in "QWERTYUIOP"],
    [(c, "letra", 1) for c in "ASDFGHJKLÇ"],
    [("SHIFT", "shift", 1.5)] + [(c, "letra", 1) for c in "ZXCVBNM"]
    + [("APAGAR", "apagar", 1.5)],
    [(a, "acento", 1) for a in "´`^~"]
    + [("ESPACO", "espaco", 4), ("CANCELAR", "cancelar", 2.2),
       ("OK", "ok", 1.8)],
]

_CAMINHOS_FONTE = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def sem_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def _carregar_fonte(tamanho):
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    for caminho in _CAMINHOS_FONTE:
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    return None


class TecladoVirtual:
    def __init__(self, largura=1280, altura=720, max_chars=30):
        self.largura, self.altura = largura, altura
        self.max_chars = max_chars
        self.texto = ""
        self.shift = False
        self.acento = None          # acento esperando a próxima vogal
        self._toque = None          # (botão, instante) para o brilho
        self._botoes = self._montar_botoes()
        self._fonte_tecla = _carregar_fonte(44)
        self._fonte_rotulo = _carregar_fonte(30)
        self._fonte_campo = _carregar_fonte(64)
        self._usa_pil = self._fonte_tecla is not None

    # ---------- lógica ----------
    def _montar_botoes(self):
        margem, espaco = 35, 10
        topo, altura_tecla = 190, 110
        botoes = []
        for i, linha in enumerate(LINHAS):
            soma = sum(p for _, _, p in linha)
            util = self.largura - 2 * margem - espaco * (len(linha) - 1)
            unidade = util / soma
            x = margem
            y = topo + i * (altura_tecla + espaco)
            for rotulo, acao, peso in linha:
                w = int(unidade * peso)
                botoes.append({"rotulo": rotulo, "acao": acao,
                               "x": int(x), "y": y, "w": w,
                               "h": altura_tecla})
                x += unidade * peso + espaco
        return botoes

    def _maiuscula(self):
        return (self.shift or not self.texto or self.texto.endswith(" "))

    def digitar(self, caractere):
        """Acrescenta um caractere respeitando o limite de tamanho."""
        if len(self.texto) < self.max_chars:
            self.texto += caractere

    def apagar(self):
        self.texto = self.texto[:-1]

    def digitar_tecla(self, caractere):
        """Para o teclado físico: letras seguem a mesma regra de maiúsculas
        (início do nome e depois de espaço); espaço não duplica."""
        if caractere == " ":
            if self.texto and not self.texto.endswith(" "):
                self.digitar(" ")
        elif caractere.isalpha():
            self.digitar(caractere.upper() if self._maiuscula()
                         else caractere.lower())
            self.shift = False
        else:
            self.digitar(caractere)

    def reiniciar(self):
        self.texto, self.shift, self.acento = "", False, None

    def botao_em(self, x, y):
        for b in self._botoes:
            if b["x"] <= x < b["x"] + b["w"] and b["y"] <= y < b["y"] + b["h"]:
                return b
        return None

    def tocar(self, x, y):
        """Processa um toque. Devolve "ok", "cancelar" ou None."""
        b = self.botao_em(x, y)
        if b is None:
            return None
        self._toque = (b, time.monotonic())
        acao = b["acao"]
        if acao == "letra":
            letra = b["rotulo"] if self._maiuscula() else b["rotulo"].lower()
            if self.acento:
                composta = unicodedata.normalize("NFC", letra + self.acento)
                if len(composta) == 1:
                    letra = composta
                self.acento = None
            self.digitar(letra)
            self.shift = False
        elif acao == "acento":
            comb = ACENTOS[b["rotulo"]]
            self.acento = None if self.acento == comb else comb
        elif acao == "shift":
            self.shift = not self.shift
        elif acao == "apagar":
            self.apagar()
        elif acao == "espaco":
            if self.texto and not self.texto.endswith(" "):
                self.digitar(" ")
        elif acao in ("ok", "cancelar"):
            return acao
        return None

    # ---------- desenho ----------
    def _rotulo(self, b):
        r = b["rotulo"]
        if b["acao"] == "letra" and not self._maiuscula():
            r = r.lower()
        return r

    def desenhar(self, frame, titulo="DIGITE O NOME"):
        """Desenha o teclado em cima do frame (que deve ter o tamanho lógico)."""
        frame[:] = (frame * 0.25).astype(np.uint8)   # escurece a câmera
        agora = time.monotonic()
        marcado = self._toque[0] if self._toque and \
            agora - self._toque[1] < 0.15 else None
        if self._usa_pil:
            self._desenhar_pil(frame, titulo, marcado, agora)
        else:
            self._desenhar_cv(frame, titulo, marcado, agora)

    def _cores(self, b, marcado):
        ativo = ((b["acao"] == "shift" and self.shift) or
                 (b["acao"] == "acento" and self.acento ==
                  ACENTOS.get(b["rotulo"])))
        if b is marcado:
            return (255, 255, 255), (0, 0, 0)         # fundo, texto (BGR)
        if ativo:
            return (0, 200, 255), (0, 0, 0)
        if b["acao"] == "ok":
            return (60, 160, 60), (255, 255, 255)
        if b["acao"] == "cancelar":
            return (50, 50, 170), (255, 255, 255)
        return (90, 90, 90), (255, 255, 255)

    def _desenhar_pil(self, frame, titulo, marcado, agora):
        from PIL import Image, ImageDraw
        img = Image.fromarray(frame[:, :, ::-1])      # BGR -> RGB
        d = ImageDraw.Draw(img)
        d.text((35, 20), titulo, font=self._fonte_rotulo,
               fill=(255, 255, 0))
        d.rounded_rectangle((35, 70, self.largura - 35, 165), radius=14,
                            outline=(255, 255, 255), width=3)
        cursor = "|" if int(agora * 2) % 2 == 0 else " "
        d.text((55, 78), self.texto + cursor, font=self._fonte_campo,
               fill=(255, 255, 255))
        for b in self._botoes:
            fundo, cor = self._cores(b, marcado)
            fundo, cor = fundo[::-1], cor[::-1]       # BGR -> RGB
            d.rounded_rectangle((b["x"], b["y"], b["x"] + b["w"],
                                 b["y"] + b["h"]), radius=12, fill=fundo)
            fonte = self._fonte_tecla if len(b["rotulo"]) == 1 \
                else self._fonte_rotulo
            r = self._rotulo(b)
            d.text((b["x"] + b["w"] / 2, b["y"] + b["h"] / 2), r,
                   font=fonte, fill=cor, anchor="mm")
        frame[:] = np.asarray(img)[:, :, ::-1]

    def _desenhar_cv(self, frame, titulo, marcado, agora):
        """Plano B sem Pillow: sem acentos na tela (mas os acentos digitados
        continuam valendo no texto)."""
        f = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, sem_acentos(titulo), (35, 50), f, 0.9,
                    (0, 255, 255), 2, cv2.LINE_AA)
        cv2.rectangle(frame, (35, 70), (self.largura - 35, 165),
                      (255, 255, 255), 2)
        cursor = "_" if int(agora * 2) % 2 == 0 else " "
        cv2.putText(frame, sem_acentos(self.texto) + cursor, (55, 140), f,
                    1.8, (255, 255, 255), 3, cv2.LINE_AA)
        for b in self._botoes:
            fundo, cor = self._cores(b, marcado)
            cv2.rectangle(frame, (b["x"], b["y"]),
                          (b["x"] + b["w"], b["y"] + b["h"]), fundo, -1)
            r = sem_acentos(self._rotulo(b))
            esc = 1.6 if len(r) == 1 else 0.9
            (tw, th), _ = cv2.getTextSize(r, f, esc, 2)
            cv2.putText(frame, r, (b["x"] + (b["w"] - tw) // 2,
                                   b["y"] + (b["h"] + th) // 2), f, esc, cor,
                        2, cv2.LINE_AA)
