"""Teste do toque: mostra onde o sistema entende que você encostou.

Serve para conferir se o toque cai exatamente no ponto tocado (principalmente
em tela cheia). Toque nos 4 cantos e no centro: o círculo deve aparecer
embaixo do seu dedo. Se aparecer deslocado, me diga em que direção e quanto.

Rodar:  python teste_toque.py            (tela cheia)
        python teste_toque.py --janela
Sair:   Q
"""
import sys

import cv2
import numpy as np

LARGURA, ALTURA = 1280, 720
JANELA = "Teste do toque"


def main():
    pontos = []

    def ao_clicar(evento, x, y, flags, param):
        if evento == cv2.EVENT_LBUTTONDOWN:
            pontos.append((x, y))
            print(f"toque em x={x}, y={y}")

    cv2.namedWindow(JANELA, cv2.WINDOW_NORMAL)
    if "--janela" not in sys.argv:
        cv2.setWindowProperty(JANELA, cv2.WND_PROP_FULLSCREEN,
                              cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(JANELA, ao_clicar)

    while True:
        quadro = np.full((ALTURA, LARGURA, 3), 40, np.uint8)
        for x in range(0, LARGURA + 1, 160):
            cv2.line(quadro, (x, 0), (x, ALTURA), (70, 70, 70), 1)
        for y in range(0, ALTURA + 1, 120):
            cv2.line(quadro, (0, y), (LARGURA, y), (70, 70, 70), 1)
        cv2.rectangle(quadro, (0, 0), (LARGURA - 1, ALTURA - 1),
                      (0, 255, 255), 4)
        cv2.putText(quadro, "TOQUE NOS 4 CANTOS E NO CENTRO  (Q sai)",
                    (200, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.1,
                    (255, 255, 255), 3, cv2.LINE_AA)
        for i, (x, y) in enumerate(pontos[-12:]):
            cv2.circle(quadro, (x, y), 22, (0, 200, 0), 3, cv2.LINE_AA)
            cv2.circle(quadro, (x, y), 3, (0, 0, 255), -1, cv2.LINE_AA)
            cv2.putText(quadro, f"{x},{y}", (x + 28, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
                        cv2.LINE_AA)
        cv2.imshow(JANELA, quadro)
        if cv2.waitKey(30) & 0xFF in (ord("q"), ord("Q")):
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
