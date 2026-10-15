"""ETAPA 3 - Achar o rosto, ver para onde a cabeça aponta e guiar 5 poses.

O programa:
  1) pede para ficar parado olhando de frente (calibra o "centro" do seu rosto)
  2) pede, uma por vez: frente, esquerda, direita, cima e baixo
  3) confirma cada pose quando você a mantém por ~1 segundo

Ainda não tira fotos: isso entra na etapa 4 (cadastro). Aqui o objetivo é
testar se a detecção das poses está boa.

Rodar:  python etapa3_rosto.py
Teclas (com a janela selecionada):
    Q  sai
    R  recomeça a sequência de poses (mantém a calibração)
    C  calibra de novo o "olhar de frente"
"""
import time

import cv2

from camera import Camera
from poses import (CalibradorDeFrente, GuiaDePoses, classificar_pose,
                   razoes_da_cabeca)
from rosto import DetectorDeRosto, desenhar_rosto

# (cv2.putText não desenha acentos, por isso os textos da tela não têm)
INSTRUCOES = {
    "centro": "OLHE DE FRENTE",
    "esquerda": "VIRE A CABECA PARA A ESQUERDA",
    "direita": "VIRE A CABECA PARA A DIREITA",
    "cima": "OLHE PARA CIMA",
    "baixo": "OLHE PARA BAIXO",
}
ROTULOS = {"centro": "FRENTE", "esquerda": "ESQUERDA", "direita": "DIREITA",
           "cima": "CIMA", "baixo": "BAIXO"}


def desenhar_barra(frame, progresso, cor=(0, 200, 0)):
    h, w = frame.shape[:2]
    x0, y0, largura, altura = 40, h - 60, w - 80, 24
    cv2.rectangle(frame, (x0, y0), (x0 + largura, y0 + altura),
                  (255, 255, 255), 2)
    preenchido = int(largura * progresso)
    if preenchido > 0:
        cv2.rectangle(frame, (x0, y0), (x0 + preenchido, y0 + altura),
                      cor, -1)


def texto(frame, msg, pos, tamanho=1.0, cor=(0, 255, 0), espessura=2):
    cv2.putText(frame, msg, pos, cv2.FONT_HERSHEY_SIMPLEX, tamanho, cor,
                espessura, cv2.LINE_AA)


def desenhar_lista(frame, guia):
    """Lista das poses no canto direito, com [x] nas já confirmadas."""
    h, w = frame.shape[:2]
    x = w - 330
    for i, passo in enumerate(guia.passos):
        feito = i < guia.indice
        atual = (i == guia.indice)
        marca = "[x]" if feito else "[ ]"
        cor = (0, 255, 0) if feito else ((0, 255, 255) if atual
                                         else (200, 200, 200))
        texto(frame, f"{marca} {ROTULOS[passo]}", (x, 50 + i * 40), 0.9, cor)


def main():
    cam = Camera(largura=1280, altura=720, preferir="csi")
    detector = DetectorDeRosto("face_landmarker.task")
    calibrador = CalibradorDeFrente(amostras=30)
    guia = GuiaDePoses()

    confirmou_ate = 0.0
    try:
        while True:
            frame = cam.read()
            if frame is None:
                continue

            pontos = detector.detectar(frame)
            razoes = razoes_da_cabeca(pontos)
            yaw, pitch = razoes if razoes else (None, None)
            desenhar_rosto(frame, pontos)

            if not calibrador.pronto:
                # fase 1: aprender como é o "olhar de frente" deste rosto
                calibrador.adicionar(yaw, pitch)
                texto(frame, "FIQUE PARADO, OLHANDO DE FRENTE", (40, 50),
                      1.1, (0, 255, 255), 3)
                if razoes is None:
                    texto(frame, "(nenhum rosto encontrado)", (40, 95), 0.9,
                          (0, 0, 255))
                desenhar_barra(frame, calibrador.progresso, (0, 200, 255))
            else:
                # fase 2: guiar as poses
                pose = classificar_pose(yaw, pitch, calibrador.base_yaw,
                                        calibrador.base_pitch)
                progresso, confirmou = guia.update(pose)
                if confirmou:
                    print(f">>> pose confirmada: {ROTULOS[guia.passos[guia.indice - 1]]}")
                    confirmou_ate = time.monotonic() + 0.7

                desenhar_lista(frame, guia)
                if guia.concluido:
                    texto(frame, "CONCLUIDO! (R recomeca)", (40, 50), 1.3,
                          (0, 255, 0), 3)
                else:
                    texto(frame, INSTRUCOES[guia.passo_atual], (40, 50), 1.1,
                          (0, 255, 255), 3)
                    desenhar_barra(frame, progresso)
                if time.monotonic() < confirmou_ate:
                    texto(frame, "OK!", (40, 120), 1.6, (0, 255, 0), 4)

                # valores ao vivo, para ajustar os limites se precisar
                lido = pose or "sem rosto"
                dados = (f"pose: {lido}   yaw {yaw:.2f}  pitch {pitch:.2f}"
                         if razoes else "pose: sem rosto")
                texto(frame, dados, (40, frame.shape[0] - 80), 0.7,
                      (255, 255, 255), 2)

            cv2.imshow("Etapa 3 - rosto", frame)
            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (ord("q"), ord("Q")):
                break
            if tecla in (ord("r"), ord("R")):
                guia.reiniciar()
            if tecla in (ord("c"), ord("C")):
                calibrador.reiniciar()
                guia.reiniciar()
    finally:
        detector.fechar()
        cam.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
