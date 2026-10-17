"""Teste: cada janela abre na tela certa? (sem câmera, sem modelos)

Mostra uma tela azul "TV" na TV e uma verde "TOUCH" no monitor de 8", em
tela cheia, e diz onde cada janela caiu. Toque (ou clique) para ver o ponto.

Rodar:  DISPLAY=:0 python teste_janelas.py          Sair: Q
        Variações para investigar: --sem-ponteiro, --sem-clique, --mover
"""
import sys
import time

import cv2
import numpy as np

from janelas import (JANELA_TOUCH, JANELA_TV, TAMANHOS, abrir_janelas,
                     onde_estao_as_janelas)
from telas import escolher_telas, listar_telas

CORES = {JANELA_TV: (90, 40, 20), JANELA_TOUCH: (40, 110, 40)}


def main():
    tv, touch = escolher_telas(listar_telas())
    cliques = []
    ponteiro = abrir_janelas(tv, touch, False, cliques,
                             usar_ponteiro="--sem-ponteiro" not in sys.argv,
                             mover="--mover" in sys.argv,
                             clicar="--sem-clique" not in sys.argv, log=print)
    time.sleep(0.5)
    onde = onde_estao_as_janelas()
    for nome in (JANELA_TV, JANELA_TOUCH):
        if nome in onde:
            w, h, x, y = onde[nome]
            print(f"{nome:6}: {w}x{h} em ({x},{y})")
        else:
            print(f"{nome:6}: não encontrei (instale: sudo apt install x11-utils)")
    if tv and touch:
        esperado_tv = (tv["largura"], tv["altura"], tv["x"], tv["y"])
        certo = onde.get(JANELA_TV) == esperado_tv and \
            onde.get(JANELA_TOUCH, (0, 0, -1, -1))[2:] == (touch["x"], touch["y"])
        print("RESULTADO:", "OK, cada janela na sua tela!" if certo
              else "as janelas NÃO estão nas telas certas")
    pontos = []
    while True:
        while cliques:
            pontos.append(cliques.pop(0))
        for nome in (JANELA_TV, JANELA_TOUCH):
            w, h = TAMANHOS[nome]
            quadro = np.full((h, w, 3), CORES[nome], np.uint8)
            cv2.rectangle(quadro, (0, 0), (w - 1, h - 1), (0, 255, 255), 6)
            cv2.putText(quadro, nome, (w // 2 - 200, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 4, (255, 255, 255), 8,
                        cv2.LINE_AA)
            if nome == JANELA_TOUCH:
                for x, y in pontos[-10:]:
                    cv2.circle(quadro, (x, y), 24, (0, 255, 0), 4, cv2.LINE_AA)
            cv2.imshow(nome, quadro)
        if cv2.waitKey(30) & 0xFF in (ord("q"), ord("Q")):
            break
    cv2.destroyAllWindows()
    if ponteiro:
        ponteiro.fechar()


if __name__ == "__main__":
    main()
