"""Teste das duas telas: abre uma janela em cada monitor, em tela cheia.

A janela da TV fica azul escura com "TV" e a do monitor touch fica verde com
"TOUCH". Em cada uma, toque (ou clique) para ver o ponto aparecer.
Se alguma janela cair na tela errada, ou as duas na mesma, me diga o que viu.

Rodar:  python teste_duas_telas.py        Sair: Q
"""
import cv2
import numpy as np

from telas import escolher_telas, listar_telas

JANELAS = {"TV": (1920, 1080, (90, 40, 20)),
           "TOUCH": (1280, 800, (40, 110, 40))}


def abrir(nome, tela, pontos):
    cv2.namedWindow(nome, cv2.WINDOW_NORMAL)
    cv2.moveWindow(nome, tela["x"], tela["y"])
    cv2.resizeWindow(nome, tela["largura"], tela["altura"])
    cv2.setWindowProperty(nome, cv2.WND_PROP_FULLSCREEN,
                          cv2.WINDOW_FULLSCREEN)

    def ao_clicar(evento, x, y, flags, param):
        if evento == cv2.EVENT_LBUTTONDOWN:
            pontos[nome].append((x, y))
    cv2.setMouseCallback(nome, ao_clicar)


def main():
    telas = listar_telas()
    print("Telas encontradas:")
    for t in telas:
        print(f"  {t['nome']}: {t['largura']}x{t['altura']} "
              f"na posição ({t['x']}, {t['y']})")
    tv, touch = escolher_telas(telas)
    if tv is None:
        print("Não consegui ler as telas (o xrandr falhou). Rode "
              "`DISPLAY=:0 xrandr --query` e me mande a saída.")
        return
    if tv is touch:
        print("Só uma tela ligada: as duas janelas vão abrir na mesma.")

    pontos = {"TV": [], "TOUCH": []}
    destino = {"TV": tv, "TOUCH": touch}
    for nome in JANELAS:
        abrir(nome, destino[nome], pontos)

    while True:
        for nome, (w, h, cor) in JANELAS.items():
            quadro = np.full((h, w, 3), cor, np.uint8)
            cv2.rectangle(quadro, (0, 0), (w - 1, h - 1), (0, 255, 255), 6)
            cv2.putText(quadro, nome, (w // 2 - 200, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 4, (255, 255, 255), 8,
                        cv2.LINE_AA)
            cv2.putText(quadro, f"{destino[nome]['nome']}  {w}x{h}  (Q sai)",
                        (40, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.4,
                        (255, 255, 255), 3, cv2.LINE_AA)
            for x, y in pontos[nome][-10:]:
                cv2.circle(quadro, (x, y), 24, (0, 255, 0), 4, cv2.LINE_AA)
            cv2.imshow(nome, quadro)
        if cv2.waitKey(30) & 0xFF in (ord("q"), ord("Q")):
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
