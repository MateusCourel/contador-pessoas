"""Mede os FPS da webcam USB em várias configurações."""
import subprocess
import time

import cv2


def ctrl(valor):
    subprocess.run(["v4l2-ctl", "-d", "/dev/video0", f"--set-ctrl={valor}"],
                   capture_output=True)


def teste(nome, largura, altura, mjpg):
    cap = cv2.VideoCapture(0)
    if mjpg:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, largura)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, altura)
    cap.set(cv2.CAP_PROP_FPS, 30)
    for _ in range(10):
        cap.read()
    n, t0 = 0, time.monotonic()
    while time.monotonic() - t0 < 4:
        ok, _ = cap.read()
        n += ok
    print(f"{nome:<28} {n / 4:5.1f} FPS", flush=True)
    cap.release()
    time.sleep(0.5)


ctrl("white_balance_automatic=1")
teste("640x480 sem compressao", 640, 480, False)
teste("640x480 MJPG", 640, 480, True)
teste("960x540 MJPG", 960, 540, True)
teste("1280x720 MJPG", 1280, 720, True)