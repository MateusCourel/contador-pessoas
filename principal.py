"""PROGRAMA PRINCIPAL (etapa 6): contagem + reconhecimento + cadastro.

Duas telas:
  TV (1920x1080)        painel para o público: contadores, câmera ao vivo
                        com as pessoas marcadas, desempenho e convites.
  Monitor touch (8")    só botões e teclado: cadastrar, ajustar a linha,
                        zerar, sair.

Rodar (no Raspberry, com o ambiente ativado):
    DISPLAY=:0 python principal.py              duas telas, tela cheia
    DISPLAY=:0 python principal.py --janela     em janelas (para testar)
    python principal.py --video teste.mp4       usa um vídeo no lugar da câmera
Opções:  --lotacao N   mostra "dentro/N" e pinta de amarelo/vermelho
Teclas:  Q (na tela inicial) sai · ESC cancela o cadastro
"""
import argparse
import os
import sys
import time
import traceback

import cv2

from banco import Banco
from console import Console
from embeddings import ExtratorDeEmbedding
from janelas import JANELA_TOUCH, JANELA_TV, abrir_janelas
from estatisticas import Configuracao, RegistroDeEventos
from nucleo import Nucleo
from painel import Painel
from segundo_plano import DetectorEmSegundoPlano
from telas import escolher_telas, listar_telas

MODELOS = {
    "face_landmarker.task": "malha do rosto (MediaPipe)",
    "gesture_recognizer.task": "gestos da mão (MediaPipe)",
    "face_recognition_sface_2021dec.onnx": "reconhecimento (SFace)",
}


class VideoComoCamera:
    """Lê um arquivo de vídeo em repetição, com a interface da Camera."""

    def __init__(self, caminho, espelhar=False):
        self._cap = cv2.VideoCapture(caminho)
        if not self._cap.isOpened():
            raise FileNotFoundError(f"não consegui abrir o vídeo: {caminho}")
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._espelhar = espelhar
        self._proximo = time.monotonic()

    def read(self):
        espera = self._proximo - time.monotonic()
        if espera > 0:
            time.sleep(espera)
        self._proximo = max(self._proximo, time.monotonic() - 0.1) + \
            1.0 / self._fps
        ok, frame = self._cap.read()
        if not ok:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
            if not ok:
                return None
        frame = cv2.resize(frame, (1280, 720))
        return cv2.flip(frame, 1) if self._espelhar else frame

    def close(self):
        self._cap.release()


def conferir_arquivos():
    faltando = [f"  - {n}  ({d})" for n, d in MODELOS.items()
                if not os.path.isfile(n)]
    if faltando:
        print("Faltam arquivos de modelo nesta pasta:")
        print("\n".join(faltando))
        print("Copie-os da pasta onde você rodou as etapas anteriores.")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--janela", action="store_true",
                    help="abre em janelas, não em tela cheia")
    ap.add_argument("--video", help="usa um arquivo de vídeo no lugar da câmera")
    ap.add_argument("--lotacao", type=int, default=None)
    ap.add_argument("--yolo", default="yolo11n_ncnn_model")
    ap.add_argument("--sem-ponteiro", action="store_true",
                    help="não usa o ponteiro virtual para escolher a tela")
    args = ap.parse_args()

    conferir_arquivos()
    from deteccao import DetectorDePessoas
    from gestos import DetectorDeGestos
    from rosto import DetectorDeRosto

    try:
        yolo = DetectorDePessoas(args.yolo, threads=3)
    except FileNotFoundError as erro:
        print(erro)
        sys.exit(1)

    tv, touch = escolher_telas(listar_telas())
    if tv is touch:
        print("Atenção: só uma tela encontrada; as duas janelas ficam sobrepostas.")
    elif tv:
        print(f"TV em {tv['nome']} ({tv['largura']}x{tv['altura']}), touch em "
              f"{touch['nome']} ({touch['largura']}x{touch['altura']})")

    if args.video:
        cam = VideoComoCamera(args.video)
    else:
        from camera import Camera
        cam = Camera(largura=1280, altura=720, preferir="csi")

    banco = Banco()
    rosto = DetectorDeRosto("face_landmarker.task", num_faces=4)
    gestos = DetectorDeGestos("gesture_recognizer.task")
    extrator = ExtratorDeEmbedding("face_recognition_sface_2021dec.onnx")
    nucleo = Nucleo(banco, extrator.extrair, rosto, gestos, Painel(),
                    Console(), Configuracao(), RegistroDeEventos(),
                    lotacao_max=args.lotacao)
    fundo = DetectorEmSegundoPlano(yolo, intervalo_min_s=0.08)   # ~12/s

    cliques = []
    ponteiro = abrir_janelas(tv, touch, args.janela, cliques,
                             usar_ponteiro=not args.sem_ponteiro,
                             log=print)
    erros_seguidos, ultimo_aviso, tecla_pendente = 0, 0.0, None
    print("Rodando. Q (na tela inicial) sai.")
    try:
        while not nucleo.sair:
            frame = cam.read()
            if frame is None:
                continue
            agora = time.monotonic()
            fundo.enviar(frame, agora)
            resultado = fundo.pegar()
            deteccoes = None
            if resultado:
                deteccoes, _, nucleo.latencia_ms = resultado
            toque = cliques.pop(0) if cliques else None
            cliques.clear()
            try:
                img_tv, img_touch = nucleo.passo(
                    frame, agora, deteccoes, toque, tecla_pendente)
                tecla_pendente = None
                erros_seguidos = 0
            except Exception:
                erros_seguidos += 1
                if agora - ultimo_aviso > 5:
                    traceback.print_exc()
                    ultimo_aviso = agora
                if erros_seguidos > 100:
                    raise
                continue
            cv2.imshow(JANELA_TV, img_tv)
            cv2.imshow(JANELA_TOUCH, img_touch)
            tecla = cv2.waitKey(1) & 0xFF
            if tecla != 255:
                tecla_pendente = tecla
    except KeyboardInterrupt:
        pass
    finally:
        fundo.parar()
        if ponteiro:
            ponteiro.fechar()
        rosto.fechar()
        gestos.fechar()
        banco.fechar()
        cam.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
