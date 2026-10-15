"""Teste de reconhecimento: mostra o nome de quem está na frente da câmera.

Serve para conferir se o cadastro da etapa 4 está bom. Mostra também a
semelhança (0 a 1): acima de 0.363 é considerado "a mesma pessoa".

Rodar:  python reconhecer_teste.py        (Q sai)
"""
import cv2

from banco import LIMITE_RECONHECER, Banco
from camera import Camera
from embeddings import ExtratorDeEmbedding
from rosto import DetectorDeRosto, desenhar_rosto


def main():
    cam = Camera(largura=1280, altura=720, preferir="csi")
    rosto = DetectorDeRosto("face_landmarker.task")
    extrator = ExtratorDeEmbedding("face_recognition_sface_2021dec.onnx")
    banco = Banco()
    try:
        while True:
            frame = cam.read()
            if frame is None:
                continue
            pontos = rosto.detectar(frame)
            desenhar_rosto(frame, pontos)
            emb = extrator.extrair(frame, pontos)
            if emb is None:
                msg, cor = ("nenhum rosto" if not pontos
                            else "chegue mais perto"), (200, 200, 200)
            else:
                nome, sim = banco.identificar(emb)
                if nome:
                    msg, cor = f"{nome}  ({sim:.2f})", (0, 255, 0)
                else:
                    msg, cor = (f"desconhecido  ({sim:.2f}, "
                                f"minimo {LIMITE_RECONHECER})"), (0, 0, 255)
            cv2.putText(frame, msg, (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                        cor, 3, cv2.LINE_AA)
            cv2.imshow("Teste de reconhecimento", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                break
    finally:
        rosto.fechar()
        banco.fechar()
        cam.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
