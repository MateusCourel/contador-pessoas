"""Telas: descobre quais monitores estão ligados e onde cada um fica.

O Pi vai ter duas telas: a TV (1920x1080) e o monitor touch de 8" (1280x800).
Este módulo lê a saída do `xrandr --query` e devolve a posição de cada uma,
para o programa abrir cada janela na tela certa.
"""
import os
import re
import subprocess

_LINHA = re.compile(
    r"^(\S+) connected(?: primary)? (\d+)x(\d+)\+(\d+)\+(\d+)")

# tamanho do monitor touch de 8" (CX080PI-A)
TOUCH_LARGURA, TOUCH_ALTURA = 1280, 800


def interpretar_xrandr(texto):
    """Lê o texto do `xrandr --query` e devolve a lista de telas ligadas
    (as desligadas, sem posição, são ignoradas):
    [{"nome", "largura", "altura", "x", "y"}]"""
    telas = []
    for linha in texto.splitlines():
        m = _LINHA.match(linha)
        if m:
            nome, w, h, x, y = m.groups()
            telas.append({"nome": nome, "largura": int(w), "altura": int(h),
                          "x": int(x), "y": int(y)})
    return telas


def listar_telas(display=":0"):
    """Roda o xrandr e devolve as telas. Lista vazia se não conseguir."""
    ambiente = dict(os.environ, DISPLAY=display)
    try:
        saida = subprocess.run(["xrandr", "--query"], capture_output=True,
                               text=True, timeout=5, env=ambiente).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return interpretar_xrandr(saida)


def escolher_telas(telas):
    """Devolve (tv, touch). O touch é a tela de 1280x800; a TV é a maior das
    outras. Se só houver uma tela, as duas são a mesma. None se não há telas."""
    if not telas:
        return None, None
    touch = next((t for t in telas
                  if (t["largura"], t["altura"]) ==
                  (TOUCH_LARGURA, TOUCH_ALTURA)), None)
    resto = [t for t in telas if t is not touch]
    tv = max(resto, key=lambda t: t["largura"] * t["altura"]) if resto \
        else None
    if touch is None:                       # nenhuma de 1280x800: a menor
        touch = min(telas, key=lambda t: t["largura"] * t["altura"])
        resto = [t for t in telas if t is not touch]
        tv = max(resto, key=lambda t: t["largura"] * t["altura"]) if resto \
            else None
    return (tv or touch), touch
