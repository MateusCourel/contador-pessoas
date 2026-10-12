"""ETAPA 2 - Detectar a mão aberta (segurar 1 segundo) e "disparar" o cadastro.

Por enquanto, ao disparar, só aparece a mensagem na tela e no terminal.
Nas próximas etapas, é aqui que entra o modo de cadastro de rostos.

Rodar:  python etapa2_gesto.py
Sair:   tecla Q
"""
import time

import cv2

from camera import Camera
from gestos import GESTO_MAO_ABERTA, DetectorDeGestos, GatilhoPorTempo


def desenhar_barra(frame, progresso):
    h, w = frame.shape[:2]
    x0, y0, largura, altura = 40, h - 60, w - 80, 24
    cv2.rectangle(frame, (x0, y0), (x0 + largura, y0 + altura),
                  (255, 255, 255), 2)
    preenchido = int(largura * progresso)
    if preenchido > 0:
        cv2.rectangle(frame, (x0, y0), (x0 + preenchido, y0 + altura),
                      (0, 200, 0), -1)


def main():
    cam = Camera(largura=1280, altura=720, preferir="csi")
    detector = DetectorDeGestos("gesture_recognizer.task")
    gatilho = GatilhoPorTempo(segurar_s=1.0, recarga_s=3.0)

    mensagem_ate = 0.0
    try:
        while True:
            frame = cam.read()
            if frame is None:
                continue

            gesto, confianca = detector.detectar(frame)
            ativo = (gesto == GESTO_MAO_ABERTA)
            progresso, disparou = gatilho.update(ativo)

            if disparou:
                print(">>> GESTO CONFIRMADO: iniciar cadastro!")
                mensagem_ate = time.monotonic() + 2.0

            texto = f"gesto: {gesto or '-'} ({confianca:.0%})"
            cv2.putText(frame, texto, (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                        1.0, (0, 255, 0), 2)
            if progresso > 0:
                desenhar_barra(frame, progresso)
            if time.monotonic() < mensagem_ate:
                cv2.putText(frame, "CADASTRO INICIADO!", (40, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 200, 255), 4)

            cv2.imshow("Etapa 2 - gesto", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                break
    finally:
        detector.fechar()
        cam.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
