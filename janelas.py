"""Abre as janelas TV e TOUCH, cada uma no seu monitor, em tela cheia.

Ordem (importante no Wayfire 0.7): ponteiro à esquerda -> abre o TOUCH;
ponteiro à direita -> abre a TV; só então as duas viram tela cheia.
"""
import os
import re
import subprocess

import cv2
import numpy as np

from ponteiro import Ponteiro

JANELA_TV, JANELA_TOUCH = "TV", "TOUCH"
TAMANHOS = {JANELA_TV: (1920, 1080), JANELA_TOUCH: (1280, 800)}


def _criar(nome, tela, em_janela, mover):
    cv2.namedWindow(nome, cv2.WINDOW_NORMAL)
    larg, alt = TAMANHOS[nome]
    if em_janela:
        if nome == JANELA_TV:                      # metade do tamanho
            cv2.resizeWindow(nome, larg // 2, alt // 2)
        else:
            cv2.resizeWindow(nome, larg, alt)
    elif tela and mover:
        cv2.moveWindow(nome, tela["x"], tela["y"])
        cv2.resizeWindow(nome, tela["largura"], tela["altura"])
    cv2.imshow(nome, np.zeros((alt, larg, 3), np.uint8))
    for _ in range(8):                             # deixa a janela abrir
        cv2.waitKey(50)


def _relatar(etapa, log):
    """Mostra onde as janelas estão agora (precisa do xwininfo)."""
    if log is None:
        return
    onde = onde_estao_as_janelas()
    partes = [f"{n}: {w}x{h}+{x}+{y}" for n, (w, h, x, y) in onde.items()]
    log(f"[janelas] {etapa}: " + ("  ".join(partes) or "(não achei)"))


def abrir_janelas(tv, touch, em_janela, cliques, usar_ponteiro=True,
                  mover=False, clicar=True, log=None):
    """Devolve o Ponteiro (ou None). cliques: lista que recebe os toques
    (x, y) na janela TOUCH. mover: pede ao sistema a posição das janelas (o
    Wayfire costuma ignorar ou interpretar errado; por padrão não pede).
    clicar: dá um clique na TV antes de abrir a janela dela, para o Wayfire
    considerar aquele monitor o ativo. log: função para relatar o caminho."""
    # evita o aviso "QFontDatabase: Cannot find font directory" do Qt
    os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts/truetype/dejavu")
    duas_telas = tv is not None and touch is not None and tv is not touch
    ponteiro = None
    if usar_ponteiro and duas_telas:
        ponteiro = Ponteiro()
        if not ponteiro.disponivel:
            print(f"[janelas] ponteiro virtual indisponível: {ponteiro.erro}")
            print("[janelas] as janelas podem abrir na mesma tela.")
            ponteiro = None

    if ponteiro:
        ponteiro.ir_para_esquerda()
    _criar(JANELA_TOUCH, touch, em_janela, mover)
    _relatar("TOUCH criada", log)
    if ponteiro:
        ponteiro.ir_para_direita()
        if clicar:
            ponteiro.clicar()
    _criar(JANELA_TV, tv, em_janela, mover)
    _relatar("TV criada", log)

    if not em_janela:
        for nome in (JANELA_TOUCH, JANELA_TV):
            cv2.setWindowProperty(nome, cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN)
        for _ in range(8):
            cv2.waitKey(50)
        _relatar("tela cheia", log)

    def ao_clicar(evento, x, y, flags, param):
        if evento == cv2.EVENT_LBUTTONDOWN:
            cliques.append((x, y))
    cv2.setMouseCallback(JANELA_TOUCH, ao_clicar)
    return ponteiro


_LINHA = re.compile(r'"(TV|TOUCH)".*?(\d+)x(\d+)\+(-?\d+)\+(-?\d+)')


def interpretar_xwininfo(texto):
    """{'TV': (largura, altura, x, y), 'TOUCH': ...} a partir do
    `xwininfo -root -tree`."""
    achados = {}
    for linha in texto.splitlines():
        m = _LINHA.search(linha)
        if m:
            nome, w, h, x, y = m.groups()
            achados[nome] = (int(w), int(h), int(x), int(y))
    return achados


def onde_estao_as_janelas(display=":0"):
    import os
    try:
        saida = subprocess.run(["xwininfo", "-root", "-tree"],
                               capture_output=True, text=True, timeout=5,
                               env=dict(os.environ, DISPLAY=display)).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    return interpretar_xwininfo(saida)
