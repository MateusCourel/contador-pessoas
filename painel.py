"""Painel: a tela principal (pensada para uma TV Full HD, 1920x1080).

Mostra a câmera ao vivo com as pessoas marcadas, os contadores grandes
(já entraram, na câmera agora, saíram, dentro agora), um gráfico das
últimas entradas, os dados de desempenho do Pi e um convite com ícone de
palma da mão para iniciar o cadastro.

Para ficar leve no Pi, a parte "de texto" é desenhada com Pillow só uma vez
por segundo (ou quando os dados mudam) e guardada; a cada quadro só se cola
a câmera por cima e se desenham as marcações das pessoas.
"""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

LARG, ALT = 1920, 1080
CAM_X, CAM_Y, CAM_W, CAM_H = 30, 110, 1260, 709        # área da câmera (16:9)
SUBTITULO = "Fatec Botucatu · 15ª Jornacitec"

# cores (RGB)
FUNDO = (11, 18, 32)
CARTAO = (20, 30, 51)
BORDA = (38, 52, 82)
TEXTO = (229, 231, 235)
SUAVE = (148, 163, 184)
CIANO = (34, 211, 238)
VERDE = (52, 211, 153)
AMARELO = (251, 191, 36)
VERMELHO = (248, 113, 113)

_FONTES = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
           "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
_FONTES_FINAS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]


def _fonte(tamanho, negrito=True):
    for caminho in (_FONTES if negrito else _FONTES_FINAS):
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    return ImageFont.load_default()


def cor_por_faixa(valor, bom, medio, maior_e_melhor=True):
    """Verde / amarelo / vermelho conforme o valor passa dos limites."""
    if maior_e_melhor:
        return VERDE if valor >= bom else AMARELO if valor >= medio else VERMELHO
    return VERDE if valor <= bom else AMARELO if valor <= medio else VERMELHO


def desenhar_palma(d, cx, cy, s, cor):
    """Ícone de mão aberta (palma) centrado em (cx, cy), tamanho s."""
    d.rounded_rectangle((cx - .30 * s, cy - .05 * s, cx + .30 * s, cy + .55 * s),
                        radius=.14 * s, fill=cor)
    for dx, altura in zip((-.225, -.075, .075, .225), (.55, .70, .66, .50)):
        x = cx + dx * s
        d.rounded_rectangle((x - .065 * s, cy + .12 * s - altura * s,
                             x + .065 * s, cy + .12 * s),
                            radius=.065 * s, fill=cor)
    # polegar
    p0, p1 = (cx - .27 * s, cy + .32 * s), (cx - .50 * s, cy + .04 * s)
    d.line([p0, p1], fill=cor, width=int(.14 * s))
    for p in (p0, p1):
        r = .07 * s
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=cor)


def _cartao(d, caixa, titulo, fonte_titulo, cor_borda=BORDA):
    x0, y0, x1, y1 = caixa
    d.rounded_rectangle(caixa, radius=22, fill=CARTAO, outline=cor_borda,
                        width=2)
    d.text((x0 + 28, y0 + 20), titulo, font=fonte_titulo, fill=SUAVE)


def _hms(segundos):
    s = int(segundos)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


class Painel:
    def __init__(self):
        self._f = {n: _fonte(t) for n, t in
                   dict(titulo=46, sub=26, rot=26, g=190, m=110, p=72,
                        texto=36, chip=30, banner=62, banner2=34).items()}
        self._f["fino"] = _fonte(28, negrito=False)
        self._chave = None
        self._estatico = None
        self._buf = None
        self._rotulos = {}

    # ---------- parte estática (re-desenhada no máximo 1x por segundo) ----
    def _desenhar_estatico(self, dados, modo, cadastro=None):
        img = Image.new("RGB", (LARG, ALT), FUNDO)
        d = ImageDraw.Draw(img)
        f = self._f

        # barra do topo
        d.text((30, 22), "CONTADOR DE PESSOAS", font=f["titulo"], fill=TEXTO)
        larg_titulo = d.textlength("CONTADOR DE PESSOAS", font=f["titulo"])
        d.text((30 + larg_titulo + 40, 52), SUBTITULO, font=f["sub"],
               fill=SUAVE, anchor="lm")
        hora = dados.get("hora", "--:--")
        d.text((LARG - 30, 22), hora, font=f["titulo"], fill=CIANO,
               anchor="ra")
        d.rectangle((CAM_X - 3, CAM_Y - 3, CAM_X + CAM_W + 2,
                     CAM_Y + CAM_H + 2), outline=BORDA, width=3)

        # coluna da direita
        x0, x1 = 1320, 1890
        _cartao(d, (x0, 110, x1, 345), "JÁ ENTRARAM", f["rot"])
        d.text((x0 + 285, 255), str(dados.get("entraram", 0)), font=f["g"],
               fill=VERDE, anchor="mm")

        _cartao(d, (x0, 360, x1, 545), "NA CÂMERA AGORA", f["rot"])
        d.text((x0 + 285, 468), str(dados.get("na_camera", 0)), font=f["m"],
               fill=CIANO, anchor="mm")

        _cartao(d, (x0, 560, x0 + 275, 705), "SAÍRAM", f["rot"])
        d.text((x0 + 137, 650), str(dados.get("sairam", 0)), font=f["p"],
               fill=TEXTO, anchor="mm")
        dentro, maximo = dados.get("dentro", 0), dados.get("lotacao_max")
        cor_dentro = TEXTO
        if maximo:
            cor_dentro = (VERMELHO if dentro >= maximo else
                          AMARELO if dentro >= 0.8 * maximo else VERDE)
        _cartao(d, (x0 + 295, 560, x1, 705), "DENTRO AGORA", f["rot"])
        d.text((x0 + 295 + 137, 650),
               f"{dentro}" + (f"/{maximo}" if maximo else ""),
               font=f["p"], fill=cor_dentro, anchor="mm")

        # gráfico das entradas recentes
        _cartao(d, (x0, 720, x1, 985), "ENTRADAS POR MINUTO",
                f["rot"])
        hist = list(dados.get("historico", []))[-30:]
        gx0, gx1, gy0, gy1 = x0 + 30, x1 - 30, 775, 960
        d.line((gx0, gy1, gx1, gy1), fill=BORDA, width=2)
        if len(hist) >= 2:
            topo = max(max(hist), 3)
            passo = (gx1 - gx0) / (len(hist) - 1)
            pts = [(gx0 + i * passo, gy1 - (v / topo) * (gy1 - gy0))
                   for i, v in enumerate(hist)]
            d.polygon(pts + [(gx1, gy1), (gx0, gy1)], fill=(18, 62, 78))
            d.line(pts, fill=CIANO, width=4, joint="curve")
            d.text((x1 - 28, 748), f"pico {max(hist)}",
                   font=f["fino"], fill=SUAVE, anchor="ra")
        else:
            d.text(((gx0 + gx1) // 2, (gy0 + gy1) // 2),
                   "coletando dados...", font=f["fino"], fill=SUAVE,
                   anchor="mm")

        # faixa de convite (palma da mão)
        self._desenhar_convite(d, modo, cadastro)

        # barra de desempenho
        d.rounded_rectangle((30, 1005, 1890, 1065), radius=18, fill=CARTAO,
                            outline=BORDA, width=2)
        fps, temp = dados.get("fps", 0.0), dados.get("temp", 0.0)
        chips = [
            ("FPS", f"{fps:.1f}", cor_por_faixa(fps, 10, 5)),
            ("TEMP", f"{temp:.0f}°C",
             cor_por_faixa(temp, 65, 75, maior_e_melhor=False)),
            ("CPU", f"{dados.get('cpu', 0):.0f}%",
             cor_por_faixa(dados.get("cpu", 0), 70, 90, False)),
            ("RAM", f"{dados.get('ram', 0):.0f}%",
             cor_por_faixa(dados.get("ram", 0), 70, 90, False)),
            ("LATÊNCIA", f"{dados.get('latencia_ms', 0):.0f} ms",
             cor_por_faixa(dados.get("latencia_ms", 0), 120, 250, False)),
            ("NO AR", _hms(dados.get("uptime_s", 0)), TEXTO),
        ]
        x = 60
        for nome, valor, cor in chips:
            d.text((x, 1035), nome, font=f["fino"], fill=SUAVE, anchor="lm")
            larg_nome = d.textlength(nome, font=f["fino"])
            d.text((x + larg_nome + 14, 1035), valor, font=f["chip"],
                   fill=cor, anchor="lm")
            x += int(larg_nome + 14 + d.textlength(valor, font=f["chip"])) + 70
        return np.asarray(img)[:, :, ::-1].copy()          # RGB -> BGR

    def _ajustar(self, d, texto, largura_max, tamanho, negrito=True):
        """Fonte do tamanho pedido, diminuída até o texto caber."""
        while tamanho > 22:
            fonte = _fonte(tamanho, negrito)
            if d.textlength(texto, font=fonte) <= largura_max:
                return fonte
            tamanho -= 4
        return _fonte(22, negrito)

    def _desenhar_convite(self, d, modo, cadastro=None):
        f = self._f
        caixa = (30, 835, 1290, 985)
        d.rounded_rectangle(caixa, radius=26, fill=CARTAO, outline=CIANO if
                            modo == "convite" else BORDA, width=3)
        if modo == "convite":
            desenhar_palma(d, 150, 909, 116, CIANO)
            d.text((270, 880), "ABRA A PALMA DA MÃO", font=f["banner"],
                   fill=TEXTO, anchor="lm")
            d.text((270, 945), "e mostre para a câmera para se cadastrar",
                   font=f["banner2"], fill=SUAVE, anchor="lm")
        elif modo == "cadastro":
            titulo, sub = cadastro or ("CADASTRO EM ANDAMENTO",
                                       "siga as instruções da tela")
            d.rounded_rectangle(caixa, radius=26, fill=CARTAO,
                                outline=AMARELO, width=3)
            d.text((660, 888), titulo,
                   font=self._ajustar(d, titulo, 1180, 62), fill=AMARELO,
                   anchor="mm")
            d.text((660, 938), sub,
                   font=self._ajustar(d, sub, 1180, 32, False), fill=TEXTO,
                   anchor="mm")
        else:
            desenhar_palma(d, 150, 909, 100, BORDA)
            d.text((270, 880), "APROXIME-SE DA CÂMERA", font=f["banner"],
                   fill=TEXTO, anchor="lm")
            d.text((270, 945), "Guardamos só números do rosto, nunca fotos.",
                   font=f["banner2"], fill=SUAVE, anchor="lm")

    # ---------- rótulos com acento, em cache ----------
    def _img_rotulo(self, texto, cor_rgb):
        chave = (texto, cor_rgb)
        if chave not in self._rotulos:
            fonte = self._f["rot"]
            caixa = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox(
                (0, 0), texto, font=fonte)
            w, h = caixa[2] + 20, caixa[3] + 14
            img = Image.new("RGB", (w, h), cor_rgb)
            ImageDraw.Draw(img).text((10, 4), texto, font=fonte,
                                     fill=(10, 14, 24))
            self._rotulos[chave] = np.asarray(img)[:, :, ::-1].copy()
            if len(self._rotulos) > 200:
                self._rotulos.pop(next(iter(self._rotulos)))
        return self._rotulos[chave]

    # ---------- montagem de cada quadro ----------
    def compor(self, camera_bgr, dados, pessoas=(), modo="ocioso", t=0.0,
               linha=None, cadastro=None, barra=None):
        """camera_bgr: quadro da câmera. pessoas: lista de dicts com
        'caixa' (x0,y0,x1,y1 normalizados), 'rotulo', 'cor' (RGB),
        e opcionalmente 'pontos' (malha do rosto, normalizada).
        linha: ((x,y),(x,y)) da linha de contagem. t: segundos (animação).
        cadastro: (título, subtítulo) mostrados na faixa durante o cadastro.
        barra: progresso 0-1 desenhado na faixa (None = sem barra)."""
        chave = (modo, tuple(cadastro or ()), tuple(sorted((k, round(v, 1) if isinstance(v, float)
                                     else tuple(v) if isinstance(v, list)
                                     else v) for k, v in dados.items())))
        if chave != self._chave:
            self._estatico = self._desenhar_estatico(dados, modo, cadastro)
            self._chave = chave
        if self._buf is None or self._buf.shape != self._estatico.shape:
            self._buf = np.empty_like(self._estatico)
        np.copyto(self._buf, self._estatico)
        quadro = self._buf

        cam = cv2.resize(camera_bgr, (CAM_W, CAM_H),
                         interpolation=cv2.INTER_LINEAR)
        if linha:
            (ax, ay), (bx, by) = linha
            p, q = (int(ax * CAM_W), int(ay * CAM_H)), \
                   (int(bx * CAM_W), int(by * CAM_H))
            cv2.line(cam, p, q, (0, 215, 255), 3, cv2.LINE_AA)
        for pessoa in pessoas:
            self._marcar(cam, pessoa)
        quadro[CAM_Y:CAM_Y + CAM_H, CAM_X:CAM_X + CAM_W] = cam

        if barra is not None and modo == "cadastro":
            x0, x1, y = 60, 1260, 964
            cv2.rectangle(quadro, (x0, y), (x1, y + 12), (82, 52, 38), -1)
            cv2.rectangle(quadro, (x0, y),
                          (x0 + int((x1 - x0) * min(max(barra, 0), 1)), y + 12),
                          (36, 191, 251), -1)

        if modo == "convite":        # contorno que pulsa para chamar atenção
            espessura = 3 + int(3 * (0.5 + 0.5 * np.sin(t * 5)))
            cv2.rectangle(quadro, (30, 835), (1290, 985), (238, 211, 34),
                          espessura, cv2.LINE_AA)
        return quadro

    def _marcar(self, cam, pessoa):
        x0, y0, x1, y1 = pessoa["caixa"]
        p0 = (int(x0 * CAM_W), int(y0 * CAM_H))
        p1 = (int(x1 * CAM_W), int(y1 * CAM_H))
        cor_rgb = pessoa.get("cor", CIANO)
        cor_bgr = cor_rgb[::-1]
        cv2.rectangle(cam, p0, p1, cor_bgr, 3, cv2.LINE_AA)
        for px, py in pessoa.get("pontos", ()):
            cv2.circle(cam, (int(px * CAM_W), int(py * CAM_H)), 2,
                       (0, 255, 0), -1)
        rotulo = self._img_rotulo(pessoa["rotulo"], cor_rgb)
        h, w = rotulo.shape[:2]
        y = max(p0[1] - h, 0)
        x = min(max(p0[0], 0), CAM_W - w)
        cam[y:y + h, x:x + w] = rotulo
