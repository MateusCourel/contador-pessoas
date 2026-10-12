"""Camera: abre a câmera CSI (flat) ou a webcam USB com a mesma interface.

Uso:
    cam = Camera()          # tenta CSI primeiro, depois USB
    frame = cam.read()      # imagem BGR (formato do OpenCV) ou None
    cam.close()
"""
import time

import cv2

try:
    from picamera2 import Picamera2
    TEM_PICAMERA2 = True
except ImportError:  # computador comum, ou biblioteca não instalada
    TEM_PICAMERA2 = False


class Camera:
    def __init__(self, largura=1280, altura=720, preferir="csi",
                 espelhar=True, indice_usb=0):
        """
        largura/altura: resolução pedida (NÃO use os 16MP inteiros, fica lento)
        preferir: "csi" (câmera do flat) ou "usb" (webcam)
        espelhar: vira a imagem como num espelho (mais natural para gestos)
        """
        self.largura = largura
        self.altura = altura
        self.espelhar = espelhar
        self._picam = None
        self._usb = None
        self.tipo = None

        ordem = ["csi", "usb"] if preferir == "csi" else ["usb", "csi"]
        for tipo in ordem:
            if tipo == "csi" and self._abrir_csi():
                break
            if tipo == "usb" and self._abrir_usb(indice_usb):
                break
        if self.tipo is None:
            raise RuntimeError(
                "Nenhuma câmera encontrada. Confira o cabo flat / a webcam e "
                "rode 'rpicam-hello --list-cameras' no terminal."
            )
        print(f"[camera] usando câmera {self.tipo.upper()} "
              f"{self.largura}x{self.altura}")

    # ------------------------------------------------------------------
    def _abrir_csi(self):
        if not TEM_PICAMERA2:
            return False
        try:
            cam = Picamera2()
            config = cam.create_preview_configuration(
                # "RGB888" no picamera2 entrega os pixels já na ordem BGR,
                # que é o que o OpenCV espera.
                main={"size": (self.largura, self.altura), "format": "RGB888"}
            )
            cam.configure(config)
            cam.start()
            time.sleep(0.5)  # deixa a exposição se ajustar
            self._picam = cam
            self.tipo = "csi"
            return True
        except Exception as erro:
            print(f"[camera] CSI indisponível: {erro}")
            return False

    def _abrir_usb(self, indice):
        cap = cv2.VideoCapture(indice)
        if not cap.isOpened():
            return False
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.largura)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.altura)
        self._usb = cap
        self.tipo = "usb"
        return True

    # ------------------------------------------------------------------
    def travar_foco(self, posicao=None):
        """Trava o autofoco (só CSI com autofoco). posicao: 0.0 (longe) a ~10
        (perto). Se a câmera não tiver autofoco, não faz nada."""
        if self._picam is None:
            return
        try:
            from libcamera import controls
            ajustes = {"AfMode": controls.AfModeEnum.Manual}
            if posicao is not None:
                ajustes["LensPosition"] = float(posicao)
            self._picam.set_controls(ajustes)
        except Exception as erro:
            print(f"[camera] não foi possível travar o foco: {erro}")

    def read(self):
        """Devolve um quadro BGR, ou None se falhar."""
        if self._picam is not None:
            frame = self._picam.capture_array()
        else:
            ok, frame = self._usb.read()
            if not ok:
                return None
        if self.espelhar:
            frame = cv2.flip(frame, 1)
        return frame

    def close(self):
        if self._picam is not None:
            self._picam.stop()
            self._picam.close()
        if self._usb is not None:
            self._usb.release()
