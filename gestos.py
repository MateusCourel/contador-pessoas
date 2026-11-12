"""Gestos: detecta a mão aberta e só dispara depois de segurar por 1 segundo.

Duas partes separadas:
  - GatilhoPorTempo: lógica pura de "segurou tempo suficiente?" (fácil de testar)
  - DetectorDeGestos: usa o MediaPipe para dizer qual gesto aparece no quadro
"""
import time

import cv2

GESTO_MAO_ABERTA = "Open_Palm"  # nome do gesto no MediaPipe


# Pares de pontos da mão (0 = pulso, 4/8/12/16/20 = pontas dos dedos) que
# formam o "esqueleto" desenhado na tela.
LIGACOES_DA_MAO = [
    (0, 1), (1, 2), (2, 3), (3, 4),            # polegar
    (0, 5), (5, 6), (6, 7), (7, 8),            # indicador
    (5, 9), (9, 10), (10, 11), (11, 12),       # médio
    (9, 13), (13, 14), (14, 15), (15, 16),     # anelar
    (13, 17), (17, 18), (18, 19), (19, 20),    # mindinho
    (0, 17),                                   # lado da palma
]


def desenhar_mao(frame, pontos):
    """Desenha o esqueleto da mão (linhas verdes, pontos vermelhos).

    pontos: lista de 21 pares (x, y) entre 0 e 1, como devolve o detector.
    Se for None ou vazia, não desenha nada."""
    if not pontos:
        return
    h, w = frame.shape[:2]
    xy = [(int(x * w), int(y * h)) for x, y in pontos]
    for a, b in LIGACOES_DA_MAO:
        cv2.line(frame, xy[a], xy[b], (0, 255, 0), 3, cv2.LINE_AA)
    for p in xy:
        cv2.circle(frame, p, 5, (0, 0, 255), -1, cv2.LINE_AA)


class GatilhoPorTempo:
    """Dispara uma vez quando o gesto fica ativo por `segurar_s` segundos.

    update(ativo, agora) devolve (progresso 0.0-1.0, disparou True/False).
    Depois de disparar, espera `recarga_s` segundos antes de poder disparar
    de novo, e a mão precisa sair da tela para "rearmar".
    """

    def __init__(self, segurar_s=1.0, recarga_s=3.0, tolerancia_s=0.25):
        self.segurar_s = segurar_s
        self.recarga_s = recarga_s
        # perdoa falhas curtas da detecção (1-2 quadros sem reconhecer)
        self.tolerancia_s = tolerancia_s
        self._inicio = None
        self._ultimo_visto = None
        self._ultimo_disparo = None
        self._precisa_soltar = False

    def update(self, ativo, agora=None):
        agora = time.monotonic() if agora is None else agora

        if ativo:
            self._ultimo_visto = agora
        elif self._inicio is not None and \
                (agora - self._ultimo_visto) > self.tolerancia_s:
            self._inicio = None  # perdeu o gesto de vez
        if not ativo and self._precisa_soltar and \
                (self._ultimo_visto is None or
                 (agora - self._ultimo_visto) > self.tolerancia_s):
            self._precisa_soltar = False  # a mão saiu: rearma

        em_recarga = (self._ultimo_disparo is not None and
                      (agora - self._ultimo_disparo) < self.recarga_s)
        if self._precisa_soltar or em_recarga:
            self._inicio = None
            return 0.0, False

        if ativo and self._inicio is None:
            self._inicio = agora
        if self._inicio is None:
            return 0.0, False

        # Só conta o tempo até o último instante em que a mão foi vista:
        # numa falha curta o relógio "congela" e nunca dispara sem a mão.
        referencia = agora if ativo else self._ultimo_visto
        progresso = min((referencia - self._inicio) / self.segurar_s, 1.0)
        if progresso >= 1.0:
            self._inicio = None
            self._ultimo_disparo = agora
            self._precisa_soltar = True
            return 1.0, True
        return progresso, False


class DetectorDeGestos:
    """Envolve o GestureRecognizer do MediaPipe."""

    def __init__(self, caminho_modelo="gesture_recognizer.task",
                 confianca_minima=0.6):
        # import aqui dentro para os testes da lógica não exigirem o mediapipe
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        opcoes = vision.GestureRecognizerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=caminho_modelo),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
        )
        self._reconhecedor = vision.GestureRecognizer.create_from_options(opcoes)
        self._confianca_minima = confianca_minima
        self._t0 = time.monotonic()
        # pontos da mão do último quadro (para desenhar o esqueleto)
        self.pontos = None

    def detectar(self, frame_bgr):
        """Devolve (nome_do_gesto, confiança) ou (None, 0.0)."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        imagem = self._mp.Image(image_format=self._mp.ImageFormat.SRGB,
                                data=rgb)
        # o modo VIDEO exige um tempo em ms que sempre aumenta
        ms = int((time.monotonic() - self._t0) * 1000)
        resultado = self._reconhecedor.recognize_for_video(imagem, ms)
        if resultado.hand_landmarks:
            self.pontos = [(p.x, p.y) for p in resultado.hand_landmarks[0]]
        else:
            self.pontos = None
        if resultado.gestures and resultado.gestures[0]:
            melhor = resultado.gestures[0][0]
            if melhor.score >= self._confianca_minima:
                return melhor.category_name, float(melhor.score)
        return None, 0.0

    def fechar(self):
        self._reconhecedor.close()
