"""Rosto: acha o rosto e seus 478 pontos (malha facial) com o MediaPipe.

Os pontos saem normalizados (x e y entre 0 e 1), e as funções de pose do
arquivo poses.py transformam isso em "olhando para a esquerda", etc.
"""
import time

import cv2


class DetectorDeRosto:
    """Envolve o FaceLandmarker do MediaPipe (um rosto por vez)."""

    def __init__(self, caminho_modelo="face_landmarker.task", num_faces=1):
        # import aqui dentro para os testes da lógica não exigirem o mediapipe
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        opcoes = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=caminho_modelo),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=num_faces,
        )
        self._reconhecedor = vision.FaceLandmarker.create_from_options(opcoes)
        self._t0 = time.monotonic()

    def detectar(self, frame_bgr):
        """Devolve a lista de 478 pontos (x, y) normalizados, ou None."""
        todos = self.detectar_todos(frame_bgr)
        return todos[0] if todos else None

    def detectar_todos(self, frame_bgr):
        """Devolve uma lista com a malha (478 pontos) de cada rosto achado."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        imagem = self._mp.Image(image_format=self._mp.ImageFormat.SRGB,
                                data=rgb)
        # o modo VIDEO exige um tempo em ms que sempre aumenta
        ms = int((time.monotonic() - self._t0) * 1000)
        resultado = self._reconhecedor.detect_for_video(imagem, ms)
        return [[(p.x, p.y) for p in rosto]
                for rosto in (resultado.face_landmarks or [])]

    def fechar(self):
        self._reconhecedor.close()


def desenhar_rosto(frame, pontos):
    """Desenha a malha de pontos (verde), a caixa do rosto e o nariz (vermelho).
    Se pontos for None, não desenha nada."""
    if not pontos:
        return
    h, w = frame.shape[:2]
    xy = [(int(x * w), int(y * h)) for x, y in pontos]
    for p in xy:
        cv2.circle(frame, p, 1, (0, 255, 0), -1)

    xs = [p[0] for p in xy]
    ys = [p[1] for p in xy]
    cv2.rectangle(frame, (min(xs), min(ys)), (max(xs), max(ys)),
                  (0, 200, 0), 2)
    cv2.circle(frame, xy[1], 6, (0, 0, 255), -1, cv2.LINE_AA)  # ponta do nariz
