"""ETAPA 1 - Ver a câmera funcionando ao vivo e medir os FPS.

Rodar:  python etapa1_camera.py
Sair:   tecla Q (com a janela da imagem selecionada) ou Ctrl+C no terminal
"""
import time

import cv2

from camera import Camera


def main():
    cam = Camera(largura=1280, altura=720, preferir="csi")
    # cam.travar_foco(posicao=1.5)  # descomente depois de testar o foco

    quadros = 0
    t0 = time.monotonic()
    fps = 0.0
    try:
        while True:
            frame = cam.read()
            if frame is None:
                print("quadro vazio, tentando de novo...")
                continue

            quadros += 1
            agora = time.monotonic()
            if agora - t0 >= 1.0:
                fps = quadros / (agora - t0)
                quadros, t0 = 0, agora

            cv2.putText(frame, f"{cam.tipo.upper()}  {fps:.1f} FPS",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                        (0, 255, 0), 2)
            cv2.imshow("Etapa 1 - camera", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                break
    finally:
        cam.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
