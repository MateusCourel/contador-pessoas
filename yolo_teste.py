"""Teste de velocidade do YOLO no Pi (detecção de pessoas + rastreamento).

Mede quantos quadros por segundo o Pi consegue com o modelo YOLO11n, em
alguns tamanhos de imagem e em dois formatos (PyTorch e NCNN, que costuma ser
bem mais rápido no Pi). Põe uma ou duas pessoas na frente da câmera durante
o teste para a medição ser realista.

Rodar (no ambiente de teste do YOLO, veja o passo a passo):
    python yolo_teste.py             mede e imprime os resultados
    python yolo_teste.py --janela    também mostra a câmera com as caixas
"""
import sys
import time

import cv2

from camera import Camera

QUADROS = 40                # quadros medidos em cada configuração
QUADROS_AQUECIMENTO = 5     # os primeiros são mais lentos, não entram na média


def medir(nome, modelo, cam, imgsz, mostrar):
    tempos, pessoas, ids = [], 0, set()
    for i in range(QUADROS + QUADROS_AQUECIMENTO):
        frame = cam.read()
        if frame is None:
            continue
        t0 = time.perf_counter()
        r = modelo.track(frame, persist=True, classes=[0], imgsz=imgsz,
                         conf=0.35, tracker="bytetrack.yaml",
                         verbose=False)[0]
        dt = time.perf_counter() - t0
        if i >= QUADROS_AQUECIMENTO:
            tempos.append(dt)
            pessoas = max(pessoas, len(r.boxes))
            if r.boxes.id is not None:
                ids.update(int(v) for v in r.boxes.id.int().cpu().tolist())
        if mostrar:
            cv2.imshow("YOLO", r.plot())
            cv2.waitKey(1)
    media = sum(tempos) / len(tempos)
    print(f"{nome:<22} imgsz={imgsz:<4} {media * 1000:6.0f} ms/quadro  "
          f"= {1 / media:5.1f} FPS   (máx. de pessoas vistas: {pessoas}, "
          f"IDs distintos: {len(ids)})")


def main():
    mostrar = "--janela" in sys.argv
    from ultralytics import YOLO

    cam = Camera(largura=1280, altura=720, preferir="csi")
    print("Aguarde: o primeiro uso baixa o modelo (cerca de 6 MB).\n")
    try:
        torch_modelo = YOLO("yolo11n.pt")
        for imgsz in (320, 416):
            medir("YOLO11n (PyTorch)", torch_modelo, cam, imgsz, mostrar)

        print("\nConvertendo para NCNN (pode demorar 1-2 minutos)...")
        try:
            caminho = torch_modelo.export(format="ncnn", imgsz=320,
                                          verbose=False)
            ncnn_modelo = YOLO(caminho)
            medir("YOLO11n (NCNN)", ncnn_modelo, cam, 320, mostrar)
        except Exception as erro:              # noqa: BLE001
            print(f"Não consegui converter para NCNN: {erro}")
    finally:
        cam.close()
        cv2.destroyAllWindows()
    print("\nMe mande estas linhas.")


if __name__ == "__main__":
    main()
