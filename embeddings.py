"""Embeddings: transforma um rosto em 128 números (modelo SFace do OpenCV).

Dois rostos da mesma pessoa dão números parecidos; de pessoas diferentes,
números diferentes. A malha facial do MediaPipe (rosto.py) já diz onde ficam
olhos, nariz e boca, então ela é usada para alinhar o rosto antes do modelo.

Modelo (baixar uma vez, na pasta do projeto):
  wget -O face_recognition_sface_2021dec.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
"""
import cv2
import numpy as np

from banco import normalizar

# Pontos da malha do MediaPipe usados no alinhamento (lado da IMAGEM:
# "olho esquerdo" aqui é o olho que aparece à esquerda na foto).
OLHO_ESQ = (33, 133)       # cantos do olho que aparece à esquerda
OLHO_DIR = (362, 263)      # cantos do olho que aparece à direita
NARIZ = 1
BOCA_ESQ = 61
BOCA_DIR = 291

LARGURA_MINIMA = 90  # px; rosto menor que isso dá embedding ruim


def _meio(pontos, a, b, w, h):
    return ((pontos[a][0] + pontos[b][0]) / 2 * w,
            (pontos[a][1] + pontos[b][1]) / 2 * h)


def face_para_sface(pontos, largura, altura, minima=LARGURA_MINIMA):
    """Monta o vetor de 15 números que o SFace espera: caixa (x, y, w, h),
    5 pontos (olho, olho, nariz, boca, boca) e um valor de confiança.

    Devolve None se não houver pontos ou se o rosto for pequeno demais."""
    if not pontos or len(pontos) < 478:
        return None
    xs = [p[0] * largura for p in pontos]
    ys = [p[1] * altura for p in pontos]
    x0, y0 = min(xs), min(ys)
    cx, cy = max(xs) - x0, max(ys) - y0
    if cx < minima:   # v0.7.1: o reconhecimento pode pedir menos que o cadastro
        return None
    olho_e = _meio(pontos, *OLHO_ESQ, largura, altura)
    olho_d = _meio(pontos, *OLHO_DIR, largura, altura)
    nariz = (pontos[NARIZ][0] * largura, pontos[NARIZ][1] * altura)
    boca_e = (pontos[BOCA_ESQ][0] * largura, pontos[BOCA_ESQ][1] * altura)
    boca_d = (pontos[BOCA_DIR][0] * largura, pontos[BOCA_DIR][1] * altura)
    return np.array([[x0, y0, cx, cy, *olho_e, *olho_d, *nariz, *boca_e,
                      *boca_d, 1.0]], dtype=np.float32)


class ExtratorDeEmbedding:
    def __init__(self, caminho_modelo="face_recognition_sface_2021dec.onnx"):
        self._modelo = cv2.FaceRecognizerSF_create(caminho_modelo, "")

    def extrair(self, frame_bgr, pontos, minima=LARGURA_MINIMA):
        """Devolve o embedding (128 números, já normalizado) ou None."""
        h, w = frame_bgr.shape[:2]
        face = face_para_sface(pontos, w, h, minima)
        if face is None:
            return None
        alinhado = self._modelo.alignCrop(frame_bgr, face)
        return normalizar(self._modelo.feature(alinhado))
