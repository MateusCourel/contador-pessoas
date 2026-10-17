"""Detecção de pessoas com o YOLO11n em NCNN (sem PyTorch).

O arquivo `yolo_teste.py` já exportou o modelo para a pasta
`yolo11n_ncnn_model/` (model.ncnn.param + model.ncnn.bin). Aqui o NCNN roda
direto, o que deixa o programa leve e evita misturar o PyTorch com o
MediaPipe no mesmo ambiente. Só precisa de:   pip install ncnn

As funções de preparar a imagem e ler a resposta do modelo são separadas da
parte que usa o NCNN, para poderem ser testadas sem o modelo.
"""
import os

import cv2
import numpy as np

TAMANHO = 320            # o modelo foi exportado com imgsz=320
COR_PREENCHIMENTO = 114  # cinza usado pelo YOLO nas bordas


def preparar_imagem(frame_bgr, tamanho=TAMANHO):
    """Redimensiona sem deformar e completa com cinza até ficar quadrada.
    Devolve (imagem tamanho x tamanho, escala, deslocamento_x, deslocamento_y)."""
    h, w = frame_bgr.shape[:2]
    escala = min(tamanho / w, tamanho / h)
    nw, nh = int(round(w * escala)), int(round(h * escala))
    redim = cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    dx, dy = (tamanho - nw) // 2, (tamanho - nh) // 2
    img = np.full((tamanho, tamanho, 3), COR_PREENCHIMENTO, np.uint8)
    img[dy:dy + nh, dx:dx + nw] = redim
    return img, escala, dx, dy


def _nms(caixas, notas, limite_iou):
    """Supressão de caixas repetidas. caixas: array (n, 4) x0,y0,x1,y1."""
    ordem = np.argsort(-notas)
    manter = []
    while len(ordem):
        i = ordem[0]
        manter.append(i)
        if len(ordem) == 1:
            break
        resto = ordem[1:]
        x0 = np.maximum(caixas[i, 0], caixas[resto, 0])
        y0 = np.maximum(caixas[i, 1], caixas[resto, 1])
        x1 = np.minimum(caixas[i, 2], caixas[resto, 2])
        y1 = np.minimum(caixas[i, 3], caixas[resto, 3])
        inter = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
        area_i = (caixas[i, 2] - caixas[i, 0]) * (caixas[i, 3] - caixas[i, 1])
        area_r = (caixas[resto, 2] - caixas[resto, 0]) * \
            (caixas[resto, 3] - caixas[resto, 1])
        iou = inter / np.maximum(area_i + area_r - inter, 1e-9)
        ordem = resto[iou < limite_iou]
    return manter


def decodificar(saida, escala, dx, dy, largura, altura, conf_minima=0.15,
                limite_nms=0.5):
    """Transforma a resposta do YOLO11 em caixas de pessoas.

    saida: matriz (84, N) (ou (N, 84)): 4 números da caixa (centro x, centro
    y, largura, altura, em pixels da imagem de 320x320) e 80 notas de classe;
    a classe 0 é "pessoa". Devolve [(x0, y0, x1, y1, nota)] normalizadas."""
    a = np.squeeze(np.asarray(saida, dtype=np.float32))
    if a.ndim != 2:
        raise ValueError(f"saída inesperada do modelo: {a.shape}")
    if a.shape[0] > a.shape[1]:
        a = a.T
    notas = a[4]
    ok = notas >= conf_minima
    if not ok.any():
        return []
    cx, cy, bw, bh = a[0][ok], a[1][ok], a[2][ok], a[3][ok]
    notas = notas[ok]
    caixas = np.stack([(cx - bw / 2 - dx) / escala,
                       (cy - bh / 2 - dy) / escala,
                       (cx + bw / 2 - dx) / escala,
                       (cy + bh / 2 - dy) / escala], axis=1)
    caixas[:, [0, 2]] = np.clip(caixas[:, [0, 2]], 0, largura) / largura
    caixas[:, [1, 3]] = np.clip(caixas[:, [1, 3]], 0, altura) / altura
    manter = _nms(caixas, notas, limite_nms)
    resultado = []
    for i in manter:
        x0, y0, x1, y1 = (float(v) for v in caixas[i])
        if x1 - x0 > 0.01 and y1 - y0 > 0.02:          # descarta caixa mínima
            resultado.append((x0, y0, x1, y1, float(notas[i])))
    return resultado


class DetectorDePessoas:
    """Envolve o modelo YOLO11n em NCNN. detectar() devolve as pessoas."""

    def __init__(self, pasta="yolo11n_ncnn_model", tamanho=TAMANHO,
                 conf_minima=0.15, threads=4):
        param = os.path.join(pasta, "model.ncnn.param")
        pesos = os.path.join(pasta, "model.ncnn.bin")
        if not (os.path.isfile(param) and os.path.isfile(pesos)):
            raise FileNotFoundError(
                f"Modelo não encontrado em '{pasta}'. Rode antes o "
                "yolo_teste.py (ele cria a pasta yolo11n_ncnn_model).")
        import ncnn      # aqui dentro: os testes não exigem o NCNN
        self._ncnn = ncnn
        self.tamanho = tamanho
        self.conf_minima = conf_minima
        self._net = ncnn.Net()
        self._net.opt.use_vulkan_compute = False
        self._net.opt.num_threads = threads
        self._net.load_param(param)
        self._net.load_model(pesos)
        try:
            self._entrada = self._net.input_names()[0]
            self._saida = sorted(self._net.output_names())[0]
        except AttributeError:               # versões antigas do ncnn
            self._entrada, self._saida = "in0", "out0"

    def detectar(self, frame_bgr):
        img, escala, dx, dy = preparar_imagem(frame_bgr, self.tamanho)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        chw = np.ascontiguousarray(rgb.transpose(2, 0, 1),
                                   dtype=np.float32) / 255.0
        with self._net.create_extractor() as ex:
            ex.input(self._entrada, self._ncnn.Mat(chw))
            _, saida = ex.extract(self._saida)
            saida = np.array(saida)
        h, w = frame_bgr.shape[:2]
        return decodificar(saida, escala, dx, dy, w, h, self.conf_minima)
