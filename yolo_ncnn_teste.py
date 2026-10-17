"""Teste rápido do YOLO em NCNN (sem PyTorch), antes do programa principal.

Abre a câmera, roda o detector por ~5 segundos, mostra quantas pessoas viu,
o tempo por quadro e salva a última imagem com as caixas em
`yolo_ncnn_teste.jpg` (abra no VS Code para conferir).

Rodar:   python yolo_ncnn_teste.py
"""
import time

import cv2

from camera import Camera
from deteccao import DetectorDePessoas


def main():
    detector = DetectorDePessoas("yolo11n_ncnn_model")
    cam = Camera(largura=1280, altura=720, preferir="csi")
    tempos, ultimo, ultimas = [], None, []
    fim = time.time() + 5
    try:
        while time.time() < fim:
            frame = cam.read()
            if frame is None:
                continue
            t0 = time.perf_counter()
            ultimas = detector.detectar(frame)
            tempos.append((time.perf_counter() - t0) * 1000)
            ultimo = frame
    finally:
        cam.close()
    if not tempos:
        print("Não recebi nenhum quadro da câmera.")
        return
    tempos = tempos[2:] or tempos                  # ignora o aquecimento
    media = sum(tempos) / len(tempos)
    print(f"{len(tempos)} quadros | {media:.1f} ms por quadro | "
          f"{1000 / media:.1f} FPS")
    print(f"Pessoas no último quadro: {len(ultimas)}")
    h, w = ultimo.shape[:2]
    for x0, y0, x1, y1, nota in ultimas:
        cv2.rectangle(ultimo, (int(x0 * w), int(y0 * h)),
                      (int(x1 * w), int(y1 * h)), (0, 255, 0), 3)
        cv2.putText(ultimo, f"{nota:.2f}", (int(x0 * w), int(y0 * h) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        print(f"  caixa ({x0:.2f},{y0:.2f})-({x1:.2f},{y1:.2f}) nota {nota:.2f}")
    cv2.imwrite("yolo_ncnn_teste.jpg", ultimo)
    print("Imagem salva em yolo_ncnn_teste.jpg")


if __name__ == "__main__":
    main()
