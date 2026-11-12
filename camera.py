"""Camera: abre a câmera CSI (flat) ou a webcam USB com a mesma interface.

Uso:
    cam = Camera()          # tenta CSI primeiro, depois USB
    frame = cam.read()      # imagem BGR (formato do OpenCV) ou None
    cam.close()

A webcam USB é aberta pela libcamera (picamera2), que entrega o quadro mais
recente com pouquíssimo atraso. Se isso falhar, cai para o OpenCV.

Cor da webcam USB: rode `python ajustar_cor.py`, escolha o ponto bom e salve.
O valor fica no arquivo ajuste_cor.txt e é aplicado sempre que a webcam abre.
"""
import os
import subprocess
import threading
import time

import cv2

try:
    from picamera2 import Picamera2
    TEM_PICAMERA2 = True
except ImportError:  # computador comum, ou biblioteca não instalada
    TEM_PICAMERA2 = False

# arquivo (ao lado deste) com o balanço de branco escolhido, em Kelvin
ARQUIVO_COR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "ajuste_cor.txt")


def definir_balanco_branco(indice, kelvin):
    """Desliga o balanço automático da webcam USB e fixa a temperatura.
    Usa o v4l2-ctl (sudo apt install v4l-utils). Devolve True se deu certo."""
    dispositivo = f"/dev/video{indice}"
    try:
        for ajuste in ("white_balance_automatic=0",
                       f"white_balance_temperature={int(kelvin)}"):
            subprocess.run(["v4l2-ctl", "-d", dispositivo,
                            f"--set-ctrl={ajuste}"],
                           check=True, capture_output=True, timeout=5)
        return True
    except Exception as erro:
        print(f"[camera] não consegui ajustar o balanço de branco: {erro}")
        return False


def manter_fps_fixo(indice):
    """Desliga o 'framerate dinâmico' da webcam USB.

    Com ele ligado, a webcam alonga a exposição quando há pouca luz e cai
    para ~15 FPS. Desligado, ela mantém ~30 FPS (a imagem pode ficar um pouco
    mais escura). Devolve True se deu certo."""
    try:
        subprocess.run(["v4l2-ctl", "-d", f"/dev/video{indice}",
                        "--set-ctrl=exposure_dynamic_framerate=0"],
                       check=True, capture_output=True, timeout=5)
        return True
    except Exception as erro:
        print(f"[camera] não consegui fixar os FPS: {erro}")
        return False


def ler_ajuste_salvo():
    """Lê o valor salvo em ajuste_cor.txt, ou None se não existir."""
    try:
        with open(ARQUIVO_COR, encoding="utf-8") as arq:
            return int(arq.read().strip())
    except (OSError, ValueError):
        return None


def aplicar_ajustes_webcam(indice):
    """Ajustes da webcam USB (FPS fixo e, se existir, balanço de branco).
    Precisa ser chamado com a webcam já aberta, porque abrir reinicia tudo."""
    manter_fps_fixo(indice)
    kelvin = ler_ajuste_salvo()
    if kelvin is not None and definir_balanco_branco(indice, kelvin):
        print(f"[camera] balanço de branco fixado em {kelvin} K")


class Camera:
    def __init__(self, largura=1280, altura=720, preferir="csi",
                 espelhar=True, indice_usb=0, trocar_rb_usb=False,
                 usb_via_libcamera=True, trocar_rb_libcamera=True):
        """
        largura/altura: resolução pedida (NÃO use os 16MP inteiros, fica lento)
        preferir: "csi" (câmera do flat) ou "usb" (webcam)
        espelhar: vira a imagem como num espelho (mais natural para gestos)
        trocar_rb_usb: troca vermelho<->azul quando a webcam é aberta pelo
            OpenCV. Desligado: nesse caminho as cores já saem certas.
        usb_via_libcamera: abre a webcam pela libcamera (menos atraso).
        trocar_rb_libcamera: nesse caminho a webcam sai com vermelho e azul
            trocados, então a troca fica ligada.
        """
        self.largura = largura
        self.altura = altura
        self.espelhar = espelhar
        self.trocar_rb_usb = trocar_rb_usb
        self.usb_via_libcamera = usb_via_libcamera
        self.trocar_rb_libcamera = trocar_rb_libcamera
        self._picam = None
        self._picam_e_usb = False
        self._usb = None
        self.tipo = None
        self.indice_usb = indice_usb
        # leitura da webcam pelo OpenCV numa thread própria (evita fila)
        self._thread = None
        self._rodando = False
        self._trava = threading.Lock()
        self._novo_quadro = threading.Event()
        self._ultimo = None

        ordem = ["csi", "usb"] if preferir == "csi" else ["usb", "csi"]
        for tipo in ordem:
            if tipo == "csi" and self._abrir_picamera(usb=False):
                break
            if tipo == "usb" and self._abrir_webcam(indice_usb):
                break
        if self.tipo is None:
            raise RuntimeError(
                "Nenhuma câmera encontrada. Confira o cabo flat / a webcam e "
                "rode 'rpicam-hello --list-cameras' no terminal."
            )
        print(f"[camera] usando câmera {self.tipo.upper()} "
              f"{self.largura}x{self.altura}")

    # ------------------------------------------------------------------
    def _abrir_picamera(self, usb):
        """Abre pela libcamera. usb=False: só a câmera do flat (CSI).
        usb=True: só a webcam USB (que a libcamera também lista)."""
        if not TEM_PICAMERA2:
            return False
        cam = None
        try:
            infos = Picamera2.global_camera_info()
            candidatas = [i for i, info in enumerate(infos)
                          if ("usb" in str(info.get("Id", "")).lower()) == usb]
            if not candidatas:
                if not usb:
                    print("[camera] nenhuma câmera CSI encontrada")
                return False
            cam = Picamera2(candidatas[0])
            config = cam.create_preview_configuration(
                main={"size": (self.largura, self.altura), "format": "RGB888"}
            )
            cam.configure(config)
            cam.start()
            time.sleep(0.5)  # deixa a exposição se ajustar
            self._picam = cam
            self._picam_e_usb = usb
            self.tipo = "usb" if usb else "csi"
            if usb:
                aplicar_ajustes_webcam(self.indice_usb)
            return True
        except Exception as erro:
            nome = "webcam via libcamera" if usb else "CSI"
            print(f"[camera] {nome} indisponível: {erro}")
            if cam is not None:
                try:
                    cam.close()
                except Exception:
                    pass
            return False

    def _abrir_webcam(self, indice):
        """Webcam USB: primeiro pela libcamera, depois pelo OpenCV."""
        if self.usb_via_libcamera and self._abrir_picamera(usb=True):
            return True
        return self._abrir_usb_opencv(indice)

    def _abrir_usb_opencv(self, indice):
        cap = cv2.VideoCapture(indice)
        if not cap.isOpened():
            return False
        # MJPG: a webcam manda a imagem já comprimida. Sem isso o OpenCV usa
        # o formato bruto (YUYV), que a C270 só entrega a ~10 FPS em 720p.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.largura)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.altura)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # menos atraso na imagem
        self._usb = cap
        self.tipo = "usb"
        self.indice_usb = indice

        aplicar_ajustes_webcam(indice)

        # thread que lê a webcam sem parar e guarda só o quadro mais novo
        self._rodando = True
        self._thread = threading.Thread(target=self._ler_usb_sem_parar,
                                        daemon=True)
        self._thread.start()
        return True

    def _ler_usb_sem_parar(self):
        while self._rodando:
            ok, frame = self._usb.read()
            if not ok:
                time.sleep(0.01)
                continue
            with self._trava:
                self._ultimo = frame
            self._novo_quadro.set()

    # ------------------------------------------------------------------
    def travar_foco(self, posicao=None):
        """Trava o autofoco (só CSI com autofoco). posicao: 0.0 (longe) a ~10
        (perto). Se a câmera não tiver autofoco, não faz nada."""
        if self._picam is None or self._picam_e_usb:
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
        """Devolve o quadro BGR mais recente, ou None se falhar."""
        if self._picam is not None:
            frame = self._picam.capture_array()
            if self._picam_e_usb and self.trocar_rb_libcamera:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        else:
            # espera um quadro novo (até 0,5 s) e pega o mais recente
            self._novo_quadro.wait(timeout=0.5)
            self._novo_quadro.clear()
            with self._trava:
                frame = self._ultimo
            if frame is None:
                return None
            frame = frame.copy()
            if self.trocar_rb_usb:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        if self.espelhar:
            frame = cv2.flip(frame, 1)
        return frame

    def close(self):
        self._rodando = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._picam is not None:
            self._picam.stop()
            self._picam.close()
        if self._usb is not None:
            self._usb.release()