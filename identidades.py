"""Identidades: liga rostos às pessoas rastreadas e lembra quem é quem.

- associar_rostos(): cada malha facial pertence à pessoa (ID do rastreador)
  cuja caixa contém o nariz.
- GerenteDeIdentidades: para cada ID guarda o nome reconhecido. Só confirma
  um nome depois de DOIS reconhecimentos seguidos iguais (evita acusar a
  pessoa errada por causa de um quadro ruim) e tenta de novo a cada
  `intervalo_s`, sem gastar processamento à toa.

É lógica pura (sem câmera nem modelos), então tem testes.
"""

# ---- quando aceitar um nome (todas as semelhanças são cosseno do SFace) ----
# nota   = média das duas melhores poses da pessoa no banco
# maxima = a melhor pose
# Um estranho às vezes bate com UMA pose por acaso; exigir a média de duas
# e uma máxima mais alta derruba esses falsos positivos.
LIMITE_NOTA = 0.42
LIMITE_MAXIMA = 0.50
MARGEM_ENTRE_PESSOAS = 0.06     # vantagem sobre o 2º colocado do banco
LIMITE_EXIBIR_NOME = LIMITE_MAXIMA          # (nome antigo, mantido)
NOTA_EXCELENTE = 0.75           # daqui para cima mostra 99%

# só tenta reconhecer rosto de frente (de lado o embedding engana)
YAW_FRENTE = (0.30, 0.70)       # 0,5 = de frente
PITCH_FRENTE = (0.42, 0.80)     # 0,6 = de frente


def confianca(nota):
    """Transforma a nota (cosseno) em uma porcentagem para a TV.
    No limite de aceitação dá 50% e em NOTA_EXCELENTE (ou mais) dá 99%.
    É uma escala de semelhança com os rostos cadastrados, não uma
    probabilidade estatística."""
    if nota <= LIMITE_NOTA:
        return max(0, int(round(50 * max(nota, 0.0) / LIMITE_NOTA)))
    frac = min((nota - LIMITE_NOTA) / (NOTA_EXCELENTE - LIMITE_NOTA), 1.0)
    return int(round(50 + 49 * frac))


def rosto_de_frente(razoes):
    """razoes = (yaw, pitch) de poses.razoes_da_cabeca, ou None."""
    if razoes is None:
        return False
    yaw, pitch = razoes
    return (YAW_FRENTE[0] <= yaw <= YAW_FRENTE[1] and
            PITCH_FRENTE[0] <= pitch <= PITCH_FRENTE[1])


def decidir(ranking, excluir=()):
    """ranking: [(nome, nota, maxima)] do banco, do mais parecido ao menos.
    Devolve (nome ou None, nota). Recusa se a nota/máxima forem baixas ou se
    o 2º colocado estiver colado no 1º (rosto ambíguo)."""
    candidatos = [r for r in ranking if r[0] not in excluir]
    if not candidatos:
        return None, 0.0
    nome, nota, maxima = candidatos[0]
    if nota < LIMITE_NOTA or maxima < LIMITE_MAXIMA:
        return None, nota
    if len(candidatos) > 1 and nota - candidatos[1][1] < MARGEM_ENTRE_PESSOAS:
        return None, nota
    return nome, nota


NARIZ = 1


def associar_rostos(rostos, caixas):
    """rostos: lista de malhas (cada uma, lista de (x, y) normalizados).
    caixas: {id: (x0, y0, x1, y1)}. Devolve {id: malha}.
    Se o nariz cair em várias caixas, vale a menor (a pessoa da frente)."""
    resultado = {}
    for pontos in rostos:
        if not pontos or len(pontos) <= NARIZ:
            continue
        nx, ny = pontos[NARIZ]
        candidatos = []
        for pid, (x0, y0, x1, y1) in caixas.items():
            if x0 <= nx <= x1 and y0 <= ny <= y1:
                candidatos.append(((x1 - x0) * (y1 - y0), pid))
        if candidatos:
            pid = min(candidatos)[1]
            resultado.setdefault(pid, pontos)
    return resultado


def largura_do_rosto(pontos, largura_img):
    """Largura da malha em pixels (para saber se o rosto está perto)."""
    if not pontos:
        return 0
    xs = [p[0] for p in pontos]
    return int(round((max(xs) - min(xs)) * largura_img))


class GerenteDeIdentidades:
    """Lembra quem é quem. Um nome só vale depois de `votos` acertos
    seguidos; depois de travado, é conferido de novo a cada `reverificar_s`
    (a porcentagem acompanha o rosto atual) e solto se errar `falhas_max`
    vezes seguidas. Um mesmo nome nunca fica em duas pessoas ao mesmo tempo."""

    def __init__(self, intervalo_s=0.7, votos=2, max_tentativas=8,
                 reverificar_s=2.5, falhas_max=3, retomar_s=6.0):
        self.intervalo_s = intervalo_s
        self.votos = votos
        self.max_tentativas = max_tentativas
        self.reverificar_s = reverificar_s
        self.falhas_max = falhas_max
        self.retomar_s = retomar_s
        self._d = {}      # id -> dicionário de estado

    def _estado(self, pid):
        return self._d.setdefault(pid, {
            "nome": None, "sim": 0.0, "ultimo": None, "sequencia": 0,
            "candidato": None, "tentativas": 0, "proxima": 0.0,
            "travado": False, "notas": [], "votos_notas": [],
            "falhas": 0, "negados": set()})

    # ---------- consulta ----------
    def nome(self, pid):
        e = self._d.get(pid)
        return e["nome"] if e and e["travado"] else None

    def semelhanca(self, pid):
        """Nota média recente (suaviza o tremido de um quadro para outro)."""
        e = self._d.get(pid)
        if not e:
            return 0.0
        if e["travado"] and e["notas"]:
            return sum(e["notas"]) / len(e["notas"])
        return e["sim"]

    def porcentagem(self, pid):
        return confianca(self.semelhanca(pid))

    def conhecido(self, pid):
        return self.nome(pid) is not None

    def rotulo(self, pid):
        return self.nome(pid) or f"Pessoa · ID {pid}"

    def rotulo_com_confianca(self, pid):
        nome = self.nome(pid)
        if nome is None:
            return f"Pessoa · ID {pid}"
        return f"{nome} · {self.porcentagem(pid)}%"

    def negados(self, pid):
        e = self._d.get(pid)
        return e["negados"] if e else set()

    def dono_do_nome(self, nome, menos_pid=None):
        """(pid, nota) de quem já está com esse nome travado, ou None."""
        melhor = None
        for pid, e in self._d.items():
            if pid == menos_pid or not e["travado"] or e["nome"] != nome:
                continue
            nota = self.semelhanca(pid)
            if melhor is None or nota > melhor[1]:
                melhor = (pid, nota)
        return melhor

    # ---------- reconhecimento ----------
    def precisa_tentar(self, pid, agora):
        e = self._estado(pid)
        if e["travado"]:
            return agora >= e["proxima"]          # reverificação
        return agora >= e["proxima"]

    def adiar(self, pid, agora, segundos):
        """Espera `segundos` antes de tentar reconhecer esta pessoa de novo
        (usado quando não apareceu rosto utilizável)."""
        e = self._estado(pid)
        e["proxima"] = max(e["proxima"], agora + segundos)

    def _destravar(self, e):
        e.update(nome=None, travado=False, candidato=None, sequencia=0,
                 notas=[], votos_notas=[], falhas=0, tentativas=0)

    def registrar(self, pid, nome, sim, agora):
        """Anota o resultado de uma tentativa (nome=None se desconhecido)."""
        e = self._estado(pid)
        e["tentativas"] += 1
        e["sim"] = sim
        if e["travado"]:
            e["proxima"] = agora + self.reverificar_s
            if nome == e["nome"]:
                e["falhas"] = 0
                e["notas"] = (e["notas"] + [sim])[-4:]
            else:
                e["falhas"] += 1
                if e["falhas"] >= self.falhas_max:
                    self._destravar(e)
                    e["proxima"] = agora + self.intervalo_s
            return e["travado"]
        e["proxima"] = agora + self.intervalo_s
        if e["tentativas"] >= self.max_tentativas:
            # não desiste para sempre: tenta de novo de vez em quando
            e["proxima"] = agora + self.retomar_s
            e["tentativas"] = self.max_tentativas - 1
        if nome is not None and nome == e["candidato"]:
            e["sequencia"] += 1
            e["votos_notas"].append(sim)
        else:
            e["candidato"], e["sequencia"] = nome, (1 if nome else 0)
            e["votos_notas"] = [sim] if nome else []
        if nome is not None and e["sequencia"] >= self.votos:
            e["nome"], e["travado"] = nome, True
            e["notas"] = e["votos_notas"][-4:]
            e["falhas"] = 0
            e["proxima"] = agora + self.reverificar_s
        return e["travado"]

    def definir(self, pid, nome, sim=1.0, agora=0.0):
        """Fixa a identidade (usado logo depois de um cadastro)."""
        e = self._estado(pid)
        e.update(nome=nome, sim=sim, travado=True, candidato=nome,
                 sequencia=self.votos, notas=[sim], falhas=0,
                 proxima=agora + self.reverificar_s)

    def resolver_unicidade(self, ids_visiveis):
        """Se o mesmo nome estiver em mais de uma pessoa visível, fica só
        quem tem a maior nota; as outras perdem o nome e passam a ser
        proibidas de usá-lo. Devolve a lista de ids rebaixados."""
        por_nome = {}
        for pid in ids_visiveis:
            nome = self.nome(pid)
            if nome:
                por_nome.setdefault(nome, []).append(pid)
        rebaixados = []
        for nome, ids in por_nome.items():
            if len(ids) < 2:
                continue
            ids.sort(key=lambda p: -self.semelhanca(p))
            for pid in ids[1:]:
                e = self._d[pid]
                e["negados"].add(nome)
                self._destravar(e)
                e["proxima"] = 0.0
                rebaixados.append(pid)
        return rebaixados

    def esquecer_ausentes(self, ids_vivos):
        for pid in [p for p in self._d if p not in ids_vivos]:
            del self._d[pid]

    def reiniciar(self):
        self._d.clear()
