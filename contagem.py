"""Contagem de entradas e saídas por uma linha virtual (lógica pura).

Como funciona: você define uma linha na imagem (por padrão, uma linha
horizontal no meio). Cada pessoa rastreada tem um ID. Quando o ID passa de um
lado da linha para o outro, conta uma entrada ou uma saída. Um pequeno
"corredor" em volta da linha evita contar duas vezes quando a pessoa fica
parada em cima dela, e quem já aparece do lado de dentro não conta como
entrada (só conta quem atravessa de verdade).

As posições são normalizadas (0 a 1). O detector/rastreador (YOLO) entrega,
para cada ID, o ponto dos pés da pessoa: meio da base da caixa.
"""


class ContadorDeEntradas:
    def __init__(self, ponto_a=(0.0, 0.5), ponto_b=(1.0, 0.5),
                 inverter=False, margem=0.03):
        """ponto_a/ponto_b: extremos da linha. 'Entrar' é cruzar da direita
        para a esquerda de quem anda de A para B; inverter=True troca isso.
        margem: largura (em fração da imagem) do corredor em volta da linha."""
        self.a, self.b = ponto_a, ponto_b
        self.inverter = inverter
        self.margem = margem
        self.entraram = 0
        self.sairam = 0
        self.pico_na_camera = 0
        self._lado = {}              # id -> -1 ou +1 (último lado confirmado)

    # ---------- geometria ----------
    def _distancia_com_sinal(self, x, y):
        """Distância (normalizada) do ponto até a linha; o sinal diz o lado."""
        ax, ay = self.a
        bx, by = self.b
        dx, dy = bx - ax, by - ay
        comprimento = (dx * dx + dy * dy) ** 0.5
        return (dx * (y - ay) - dy * (x - ax)) / comprimento

    # ---------- uso ----------
    @property
    def dentro(self):
        """Saldo de entradas menos saídas (nunca negativo)."""
        return max(self.entraram - self.sairam, 0)

    def atualizar(self, pessoas):
        """pessoas: dict {id: (x, y)} do quadro atual.
        Devolve a lista de eventos [(id, 'entrou' | 'saiu')]."""
        eventos = []
        self.pico_na_camera = max(self.pico_na_camera, len(pessoas))
        for pid, (x, y) in pessoas.items():
            d = self._distancia_com_sinal(x, y)
            if abs(d) < self.margem:
                continue                        # dentro do corredor: ignora
            lado = 1 if d > 0 else -1
            antes = self._lado.get(pid)
            self._lado[pid] = lado
            if antes is None or antes == lado:
                continue                        # apareceu agora ou não cruzou
            entrou = (lado > 0) != self.inverter
            if entrou:
                self.entraram += 1
            else:
                self.sairam += 1
            eventos.append((pid, "entrou" if entrou else "saiu"))
        # esquece quem sumiu do quadro (o ID não volta a ser usado)
        for pid in [p for p in self._lado if p not in pessoas]:
            del self._lado[pid]
        return eventos

    def reiniciar(self):
        self.entraram = self.sairam = self.pico_na_camera = 0
        self._lado.clear()
