"""Exporta o YOLO11n para NCNN em outro tamanho de entrada (retangular).

Rode no ambiente que TEM o ultralytics (o mesmo do yolo_teste.py), não no
ambiente do contador:

    python exportar_yolo.py                      # 448x256 (recomendado)
    python exportar_yolo.py --largura 576 --altura 320
    python exportar_yolo.py --largura 320 --altura 320   # o modelo antigo

Por que retangular: a câmera é 16:9. Num modelo quadrado 320x320 a imagem
vira 320x180 e o resto (quase metade) é faixa cinza inútil. Um modelo
448x256 gasta quase o mesmo tempo, mas enxerga quem está longe com 40% mais
detalhe. Largura e altura precisam ser múltiplos de 32.

Saída: pasta yolo11n_ncnn_model_<L>x<A>  (copie para ~/contador-pessoas).
"""
import argparse
import os
import shutil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--largura", type=int, default=448)
    ap.add_argument("--altura", type=int, default=256)
    ap.add_argument("--pesos", default="yolo11n.pt")
    args = ap.parse_args()
    for v in (args.largura, args.altura):
        if v % 32:
            raise SystemExit("largura e altura precisam ser múltiplos de 32")
    from ultralytics import YOLO
    caminho = YOLO(args.pesos).export(format="ncnn",
                                      imgsz=(args.altura, args.largura))
    destino = f"yolo11n_ncnn_model_{args.largura}x{args.altura}"
    if os.path.isdir(destino):
        shutil.rmtree(destino)
    shutil.move(str(caminho), destino)
    print(f"\nPronto: {destino}")
    print("Copie essa pasta para ~/contador-pessoas e teste com:")
    print(f"  python yolo_ncnn_teste.py --yolo {destino}")


if __name__ == "__main__":
    main()
