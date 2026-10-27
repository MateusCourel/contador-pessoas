"""Contagem de entradas e saídas por uma linha virtual (lógica pura).

Como funciona: você define uma linha na imagem (por padrão, uma linha
horizontal no meio). Cada pessoa rastreada tem um ID. Quando o ID passa de um
lado da linha para o outro, conta uma entrada ou uma saída. Um pequeno
"corredor" em volta da linha evita contar duas vezes quando a pessoa fica
parada em cima dela, e quem já aparece do lado de dentro não conta como
entrada (só conta quem atravessa de verdade).

Quem só é visto depois de já ter passado da linha (a pessoa pequena e longe
demora a ser detectada, e quando aparece já está dentro) também conta: se uma
pessoa NOVA nasce perto da linha e se afasta dela, entende-se que ela a
atravessou ("inferência de nascimento"). Isso só vale para pistas que nasceram
com o programa já rodando há alguns segundos, para não contar quem já estava
na sala quando ele abriu.

As posições são normalizadas (0 a 1). O detector/rastreador (YOLO) entrega,
para cada ID, o ponto dos pés da pessoa: meio da base da caixa.
"""


ZONA_NASCIMENTO = 0.22     # nasce até esta distância da linha (fração)
DESLOCAMENTO = 0.06        # e se afasta pelo menos isto: então atravessou
VIDA_DA_INFERENCIA_S = 4.0  # só confere nos primeiros segundos da pista
IDADE_MAXIMA_AO_VER_S = 0.6  # "nova" = a pista tinha no máximo isto de vida
GRACA_S = 3.0              # sem inferir logo que o programa/linha reinicia


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
        self._nascimento = {}        # id -> (d ao nascer, instante) a conferir
        self._livre_desde = None     # a partir daqui pode inferir
        self.inferidos = 0           # quantas contagens vieram da inferência
        self.inferir_nascimento = True

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

    def _evento(self, lado, pid, eventos):
        entrou = (lado > 0) != self.inverter
        if entrou:
            self.entraram += 1
        else:
            self.sairam += 1
        eventos.append((pid, "entrou" if entrou else "saiu"))

    def atualizar(self, pessoas, agora=None, idades=None):
        """pessoas: dict {id: (x, y)} do quadro atual.
        agora/idades (opcionais): instante atual e quantos segundos de vida
        tem cada pista; ligam a inferência de quem nasceu depois da linha.
        Devolve a lista de eventos [(id, 'entrou' | 'saiu')]."""
        eventos = []
        self.pico_na_camera = max(self.pico_na_camera, len(pessoas))
        if agora is not None and self._livre_desde is None:
            self._livre_desde = agora + GRACA_S
        for pid, (x, y) in pessoas.items():
            d = self._distancia_com_sinal(x, y)
            primeira_vez = pid not in self._lado and \
                pid not in self._nascimento
            if (primeira_vez and agora is not None and idades is not None
                    and self.inferir_nascimento
                    and idades.get(pid, 99) <= IDADE_MAXIMA_AO_VER_S
                    and abs(d) <= ZONA_NASCIMENTO
                    and agora - idades[pid] >= self._livre_desde):
                self._nascimento[pid] = (d, agora)
            if abs(d) < self.margem:
                continue                        # dentro do corredor: ignora
            lado = 1 if d > 0 else -1
            antes = self._lado.get(pid)
            self._lado[pid] = lado
            if antes is not None and antes != lado:
                self._nascimento.pop(pid, None)  # cruzou de verdade
                self._evento(lado, pid, eventos)
                continue
            nasc = self._nascimento.get(pid)
            if nasc is not None:
                d0, t0 = nasc
                if agora - t0 > VIDA_DA_INFERENCIA_S:
                    del self._nascimento[pid]
                elif (d - d0) * lado >= DESLOCAMENTO:
                    # nasceu junto da linha e já se afastou dela, para o
                    # lado `lado`: atravessou sem ser visto
                    del self._nascimento[pid]
                    self.inferidos += 1
                    self._evento(lado, pid, eventos)
        # esquece quem sumiu do quadro (o ID não volta a ser usado)
        for pid in [p for p in self._lado if p not in pessoas]:
            del self._lado[pid]
        for pid in [p for p in self._nascimento if p not in pessoas]:
            del self._nascimento[pid]
        return eventos

    def mover_linha(self, ponto_a, ponto_b, inverter):
        """Muda a linha sem contar ninguém por engano (esquece os lados)."""
        self.a, self.b, self.inverter = ponto_a, ponto_b, inverter
        self._lado.clear()
        self._nascimento.clear()
        self._livre_desde = None

    def reiniciar(self):
        self.entraram = self.sairam = self.pico_na_camera = 0
        self.inferidos = 0
        self._lado.clear()
        self._nascimento.clear()
