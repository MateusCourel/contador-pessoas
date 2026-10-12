"""Gestos: detecta a mão aberta e só dispara depois de segurar por 1 segundo.

Duas partes separadas:
  - GatilhoPorTempo: lógica pura de "segurou tempo suficiente?" (fácil de testar)
  - DetectorDeGestos: usa o MediaPipe para dizer qual gesto aparece no quadro
"""
import time

import cv2

GESTO_MAO_ABERTA = "Open_Palm"  # nome do gesto no MediaPipe


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

    def detectar(self, frame_bgr):
        """Devolve (nome_do_gesto, confiança) ou (None, 0.0)."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        imagem = self._mp.Image(image_format=self._mp.ImageFormat.SRGB,
                                data=rgb)
        # o modo VIDEO exige um tempo em ms que sempre aumenta
        ms = int((time.monotonic() - self._t0) * 1000)
        resultado = self._reconhecedor.recognize_for_video(imagem, ms)
        if resultado.gestures and resultado.gestures[0]:
            melhor = resultado.gestures[0][0]
            if melhor.score >= self._confianca_minima:
                return melhor.category_name, float(melhor.score)
        return None, 0.0

    def fechar(self):
        self._reconhecedor.close()
