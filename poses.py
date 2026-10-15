"""Poses da cabeça: lógica pura (sem câmera e sem MediaPipe), fácil de testar.

Como funciona:
  - razoes_da_cabeca(pontos): olha onde a ponta do nariz está dentro do rosto
    e devolve duas razões (yaw = esquerda/direita, pitch = cima/baixo).
  - CalibradorDeFrente: mede as razões com a pessoa olhando de frente. Cada
    rosto é diferente, então tudo é comparado com essa "linha de base".
  - classificar_pose(...): diz "centro", "esquerda", "direita", "cima" ou
    "baixo" (esquerda/direita são do ponto de vista de quem está na frente da
    câmera, como num espelho).
  - GuiaDePoses: conduz a sequência de poses e confirma cada uma quando a
    pessoa a mantém por um tempo.
"""
import time

# Índices dos pontos da malha facial do MediaPipe (478 pontos)
PONTA_DO_NARIZ = 1
TESTA = 10
QUEIXO = 152
BOCHECHA_A = 234   # um lado do rosto
BOCHECHA_B = 454   # o outro lado

# O quanto a cabeça precisa se afastar do "centro" para contar como virada.
# Se alguma pose ficar difícil/fácil demais, ajuste aqui.
LIMITE_YAW = 0.10
LIMITE_PITCH = 0.05

# Se "cima" e "baixo" aparecerem trocados no seu teste, mude para True.
INVERTER_CIMA_BAIXO = False

POSES = ("centro", "esquerda", "direita", "cima", "baixo")


def razoes_da_cabeca(pontos):
    """pontos: lista de (x, y) normalizados (0 a 1) da malha facial.

    Devolve (yaw, pitch):
      yaw   ~0.5 de frente; sobe quando o nariz vai para a DIREITA da imagem
      pitch ~0.6 de frente; desce quando o nariz sobe (olhar para cima)
    ou None se não houver pontos suficientes."""
    if not pontos or len(pontos) <= max(BOCHECHA_A, BOCHECHA_B):
        return None
    nariz_x, nariz_y = pontos[PONTA_DO_NARIZ]
    xa, xb = pontos[BOCHECHA_A][0], pontos[BOCHECHA_B][0]
    esquerda, direita = min(xa, xb), max(xa, xb)  # na imagem, não no rosto
    largura = direita - esquerda
    altura = pontos[QUEIXO][1] - pontos[TESTA][1]
    if largura <= 1e-6 or altura <= 1e-6:
        return None
    yaw = (nariz_x - esquerda) / largura
    pitch = (nariz_y - pontos[TESTA][1]) / altura
    return yaw, pitch


def classificar_pose(yaw, pitch, base_yaw=0.5, base_pitch=0.6,
                     limite_yaw=LIMITE_YAW, limite_pitch=LIMITE_PITCH):
    """Devolve 'centro', 'esquerda', 'direita', 'cima' ou 'baixo'
    (None se yaw/pitch forem None)."""
    if yaw is None or pitch is None:
        return None
    d_yaw = (yaw - base_yaw) / limite_yaw
    d_pitch = (pitch - base_pitch) / limite_pitch
    if abs(d_yaw) < 1 and abs(d_pitch) < 1:
        return "centro"
    if abs(d_yaw) >= abs(d_pitch):
        return "direita" if d_yaw > 0 else "esquerda"
    # nariz sobe na imagem -> pitch diminui -> cabeça olhando para cima
    cima = d_pitch < 0
    if INVERTER_CIMA_BAIXO:
        cima = not cima
    return "cima" if cima else "baixo"


class CalibradorDeFrente:
    """Junta amostras com a pessoa olhando de frente e tira a média.

    Com exigir_estavel=True, só calibra quando as últimas `amostras` leituras
    estão paradas (variação pequena). Isso evita guardar como "frente" um
    momento em que a pessoa ainda mexia a cabeça. Se nunca ficar estável,
    aceita a janela mais recente depois de `amostras * paciencia` leituras."""

    def __init__(self, amostras=30, exigir_estavel=False, var_yaw=0.06,
                 var_pitch=0.04, paciencia=6):
        self.amostras = amostras
        self.exigir_estavel = exigir_estavel
        self.var_yaw = var_yaw
        self.var_pitch = var_pitch
        self.paciencia = paciencia
        self.base_yaw = 0.5
        self.base_pitch = 0.6
        self.reiniciar()

    @property
    def pronto(self):
        return self._pronto

    @property
    def progresso(self):
        if self._pronto:
            return 1.0
        return min(len(self._yaw) / self.amostras, 1.0) * \
            (0.95 if self.exigir_estavel else 1.0)

    def _estavel(self):
        return (max(self._yaw) - min(self._yaw) <= self.var_yaw and
                max(self._pitch) - min(self._pitch) <= self.var_pitch)

    def adicionar(self, yaw, pitch):
        """Devolve True quando a calibração terminou."""
        if self._pronto:
            return True
        if yaw is None or pitch is None:
            return False
        self._yaw.append(yaw)
        self._pitch.append(pitch)
        self._vistas += 1
        if self.exigir_estavel:
            self._yaw = self._yaw[-self.amostras:]
            self._pitch = self._pitch[-self.amostras:]
            cheia = len(self._yaw) >= self.amostras
            cansou = self._vistas >= self.amostras * self.paciencia
            self._pronto = cheia and (self._estavel() or cansou)
        else:
            self._pronto = len(self._yaw) >= self.amostras
        if self._pronto:
            self.base_yaw = sum(self._yaw) / len(self._yaw)
            self.base_pitch = sum(self._pitch) / len(self._pitch)
        return self._pronto

    def reiniciar(self):
        self._yaw, self._pitch = [], []
        self._vistas = 0
        self._pronto = False


class Suavizador:
    """Média móvel exponencial de (yaw, pitch): tira a tremida dos pontos.
    alpha menor = mais suave (e um pouco mais lento para reagir)."""

    def __init__(self, alpha=0.5):
        self.alpha = alpha
        self._valor = None

    def atualizar(self, yaw, pitch):
        if yaw is None or pitch is None:
            self._valor = None
            return None, None
        if self._valor is None:
            self._valor = (yaw, pitch)
        else:
            a = self.alpha
            self._valor = (a * yaw + (1 - a) * self._valor[0],
                           a * pitch + (1 - a) * self._valor[1])
        return self._valor

    def reiniciar(self):
        self._valor = None


class GuiaDePoses:
    """Conduz a sequência de poses. Cada pose só é confirmada depois de
    mantida por `segurar_s` segundos; depois há uma pequena pausa antes do
    próximo passo (é nesse instante que, no cadastro, a foto será tirada).

    update(pose_atual, agora) devolve (progresso 0.0-1.0, confirmou True/False).
    """

    def __init__(self, passos=POSES, segurar_s=0.8, pausa_s=0.7,
                 tolerancia_s=0.2):
        self.passos = tuple(passos)
        self.segurar_s = segurar_s
        self.pausa_s = pausa_s
        self.tolerancia_s = tolerancia_s
        self.indice = 0
        self._inicio = None
        self._ultimo_visto = None
        self._pausa_ate = None

    @property
    def concluido(self):
        return self.indice >= len(self.passos)

    @property
    def passo_atual(self):
        return None if self.concluido else self.passos[self.indice]

    def reiniciar(self):
        self.indice = 0
        self._inicio = None
        self._ultimo_visto = None
        self._pausa_ate = None

    def update(self, pose_atual, agora=None):
        agora = time.monotonic() if agora is None else agora
        if self.concluido:
            return 1.0, False
        if self._pausa_ate is not None and agora < self._pausa_ate:
            return 0.0, False

        ativo = (pose_atual == self.passo_atual)
        if ativo:
            self._ultimo_visto = agora
            if self._inicio is None:
                self._inicio = agora
        elif self._inicio is not None and \
                (agora - self._ultimo_visto) > self.tolerancia_s:
            self._inicio = None  # perdeu a pose de vez

        if self._inicio is None:
            return 0.0, False

        # Só conta o tempo até a última vez que a pose foi vista (o relógio
        # "congela" numa falha curta e nunca confirma sem a pessoa na pose).
        referencia = agora if ativo else self._ultimo_visto
        progresso = min((referencia - self._inicio) / self.segurar_s, 1.0)
        if progresso >= 1.0:
            self.indice += 1
            self._inicio = None
            self._pausa_ate = agora + self.pausa_s
            return 1.0, True
        return progresso, False
