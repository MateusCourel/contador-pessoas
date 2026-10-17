"""Texto com acentos em cima de imagens do OpenCV (usa o Pillow).

O cv2.putText não sabe desenhar "ã", "ç", "é"... Aqui só a área do texto é
convertida para Pillow e devolvida, então é rápido o bastante para a tela
touch (que muda pouco).
"""
import cv2
import numpy as np
from PIL import Image, ImageDraw

from painel import _fonte

_cache = {}


def fonte(tamanho, negrito=True):
    chave = (tamanho, negrito)
    if chave not in _cache:
        _cache[chave] = _fonte(tamanho, negrito)
    return _cache[chave]


def medir(txt, tamanho, negrito=True):
    """(largura, altura) em pixels do texto."""
    caixa = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox(
        (0, 0), txt, font=fonte(tamanho, negrito))
    return caixa[2], caixa[3]


def texto(frame, txt, pos, tamanho=32, cor=(255, 255, 255), ancora="la",
          negrito=True):
    """Desenha `txt` em `frame` (BGR). pos = (x, y) conforme a âncora do
    Pillow ("la" = canto esquerdo/topo, "ma" = meio/topo, "mm" = centro).
    cor em BGR. Devolve (x0, y0, x1, y1) da área usada."""
    f = fonte(tamanho, negrito)
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    bx0, by0, bx1, by1 = d0.textbbox((int(pos[0]), int(pos[1])), txt, font=f,
                                     anchor=ancora)
    h, w = frame.shape[:2]
    x0, y0 = max(bx0 - 2, 0), max(by0 - 2, 0)
    x1, y1 = min(bx1 + 2, w), min(by1 + 2, h)
    if x1 <= x0 or y1 <= y0:
        return (x0, y0, x0, y0)
    patch = Image.fromarray(cv2.cvtColor(frame[y0:y1, x0:x1],
                                         cv2.COLOR_BGR2RGB))
    ImageDraw.Draw(patch).text((pos[0] - x0, pos[1] - y0), txt, font=f,
                               fill=(cor[2], cor[1], cor[0]), anchor=ancora)
    frame[y0:y1, x0:x1] = cv2.cvtColor(np.asarray(patch), cv2.COLOR_RGB2BGR)
    return (x0, y0, x1, y1)
