"""Rastreador: dá um número (ID) a cada pessoa e o mantém quadro a quadro.

É uma versão enxuta da ideia do ByteTrack (a mesma do YOLO "track"), feita
só com Python e sem PyTorch:
  1) cada pessoa já rastreada "prevê" onde estará (continua andando na mesma
     direção);
  2) as detecções fortes são ligadas às pessoas pela sobreposição das caixas
     (IoU); depois, as detecções fracas tentam recuperar quem sobrou
     (é o truque do ByteTrack para pessoas parcialmente escondidas);
  3) uma detecção forte que ninguém "reivindicou" vira uma pessoa nova, mas só
     é confirmada (e contada) depois de aparecer em alguns quadros seguidos,
     para um vulto de 1 quadro não virar "pessoa";
  4) quem some fica guardado por um tempo (se reaparecer, mantém o ID).

Todas as caixas são normalizadas (0 a 1): (x0, y0, x1, y1).
"""
from dataclasses import dataclass


def iou(a, b):
    """Sobreposição (0 a 1) entre duas caixas (x0, y0, x1, y1)."""
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(ix1 - ix0, 0.0), max(iy1 - iy0, 0.0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    uniao = area_a + area_b - inter
    return inter / uniao if uniao > 0 else 0.0


@dataclass
class Pista:
    """Uma pessoa rastreada."""
    id: int
    caixa: tuple            # (x0, y0, x1, y1) normalizada
    conf: float
    visivel: bool           # False = sumiu há pouco (ainda guardada)
    acertos: int = 1
    confirmada: bool = False
    ultima_vez: float = 0.0
    vel: tuple = (0.0, 0.0)  # deslocamento por segundo do centro (x, y)

    @property
    def centro(self):
        x0, y0, x1, y1 = self.caixa
        return (x0 + x1) / 2, (y0 + y1) / 2

    @property
    def pes(self):
        """Ponto dos pés: meio da base da caixa."""
        x0, y0, x1, y1 = self.caixa
        return (x0 + x1) / 2, y1

    @property
    def altura(self):
        return self.caixa[3] - self.caixa[1]


class Rastreador:
    def __init__(self, conf_alta=0.35, conf_nova=0.45, iou_minimo=0.25,
                 iou_minimo_fraca=0.45, confirmar=2, guardar_s=1.5):
        """
        conf_alta:  a partir daqui a detecção é "forte"
        conf_nova:  confiança mínima para abrir uma pessoa nova
        iou_minimo: sobreposição mínima para ligar detecção forte a pessoa
        confirmar:  quadros seguidos até a pessoa nova ser confirmada
        guardar_s:  quanto tempo guarda quem sumiu (para manter o ID)
        """
        self.conf_alta = conf_alta
        self.conf_nova = conf_nova
        self.iou_minimo = iou_minimo
        self.iou_minimo_fraca = iou_minimo_fraca
        self.confirmar = confirmar
        self.guardar_s = guardar_s
        self._pistas = []
        self._proximo_id = 1

    # ---------- partes internas ----------
    @staticmethod
    def _prever(pista, agora):
        dt = min(max(agora - pista.ultima_vez, 0.0), 0.5)
        dx, dy = pista.vel[0] * dt, pista.vel[1] * dt
        x0, y0, x1, y1 = pista.caixa
        return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)

    def _ligar(self, pistas, deteccoes, previstas, minimo):
        """Liga pistas a detecções pelo maior IoU (guloso).
        Devolve (pares [(i_pista, i_deteccao)], pistas_soltas, deteccoes_soltas)."""
        candidatos = []
        for i in pistas:
            for j, det in deteccoes:
                valor = iou(previstas[i], det[:4])
                if valor >= minimo:
                    candidatos.append((valor, i, j))
        candidatos.sort(reverse=True)
        usadas_p, usadas_d, pares = set(), set(), []
        for _, i, j in candidatos:
            if i in usadas_p or j in usadas_d:
                continue
            usadas_p.add(i)
            usadas_d.add(j)
            pares.append((i, j))
        soltas_p = [i for i in pistas if i not in usadas_p]
        soltas_d = [(j, d) for j, d in deteccoes if j not in usadas_d]
        return pares, soltas_p, soltas_d

    def _atualizar_pista(self, pista, det, agora):
        centro_antes = pista.centro
        dt = agora - pista.ultima_vez
        pista.caixa = tuple(det[:4])
        pista.conf = det[4]
        if 0.02 < dt < 1.0:
            cx, cy = pista.centro
            vx, vy = (cx - centro_antes[0]) / dt, (cy - centro_antes[1]) / dt
            pista.vel = (0.5 * pista.vel[0] + 0.5 * vx,
                         0.5 * pista.vel[1] + 0.5 * vy)
        pista.ultima_vez = agora
        pista.acertos += 1
        pista.visivel = True
        if pista.acertos >= self.confirmar:
            pista.confirmada = True

    # ---------- uso ----------
    def atualizar(self, deteccoes, agora):
        """deteccoes: lista de (x0, y0, x1, y1, conf) normalizadas.
        Devolve as pistas confirmadas (visíveis ou sumidas há pouco)."""
        previstas = {id(p): self._prever(p, agora) for p in self._pistas}
        # índices por posição na lista, para o ligar() ser simples
        idx = {i: p for i, p in enumerate(self._pistas)}
        prev_i = {i: previstas[id(p)] for i, p in idx.items()}

        fortes = [(j, d) for j, d in enumerate(deteccoes)
                  if d[4] >= self.conf_alta]
        fracas = [(j, d) for j, d in enumerate(deteccoes)
                  if d[4] < self.conf_alta]

        pares, soltas, fortes_soltas = self._ligar(list(idx), fortes, prev_i,
                                                   self.iou_minimo)
        vistas = set()
        for i, j in pares:
            self._atualizar_pista(idx[i], deteccoes[j], agora)
            vistas.add(i)

        # segunda chance: detecções fracas para quem sobrou
        pares2, soltas, _ = self._ligar(soltas, fracas, prev_i,
                                        self.iou_minimo_fraca)
        for i, j in pares2:
            self._atualizar_pista(idx[i], deteccoes[j], agora)
            vistas.add(i)

        for i in soltas:
            idx[i].visivel = False
            if not idx[i].confirmada:
                idx[i].acertos = 0           # vulto que falhou: recomeça

        # pessoas novas
        for _, d in fortes_soltas:
            if d[4] < self.conf_nova:
                continue
            self._pistas.append(Pista(
                id=self._proximo_id, caixa=tuple(d[:4]), conf=d[4],
                visivel=True, acertos=1, ultima_vez=agora,
                confirmada=self.confirmar <= 1))
            self._proximo_id += 1

        # esquece quem sumiu há tempo demais (e vultos nunca confirmados)
        self._pistas = [
            p for p in self._pistas
            if (agora - p.ultima_vez) <= (self.guardar_s if p.confirmada
                                          else 0.4)]
        return [p for p in self._pistas if p.confirmada]

    def reiniciar(self):
        self._pistas = []
