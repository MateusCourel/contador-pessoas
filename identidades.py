"""Identidades: liga rostos às pessoas rastreadas e lembra quem é quem.

- associar_rostos(): cada malha facial pertence à pessoa (ID do rastreador)
  cuja caixa contém o nariz.
- GerenteDeIdentidades: para cada ID guarda o nome reconhecido. Só confirma
  um nome depois de DOIS reconhecimentos seguidos iguais (evita acusar a
  pessoa errada por causa de um quadro ruim) e tenta de novo a cada
  `intervalo_s`, sem gastar processamento à toa.

É lógica pura (sem câmera nem modelos), então tem testes.
"""

# Semelhança mínima para MOSTRAR um nome na TV (mais rígida que a do banco,
# que é 0.363): um nome errado em público é pior que "Pessoa · ID n".
LIMITE_EXIBIR_NOME = 0.45

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
    def __init__(self, intervalo_s=0.7, votos=2, max_tentativas=8):
        self.intervalo_s = intervalo_s
        self.votos = votos
        self.max_tentativas = max_tentativas
        self._d = {}      # id -> dicionário de estado

    def _estado(self, pid):
        return self._d.setdefault(pid, {
            "nome": None, "sim": 0.0, "ultimo": None, "sequencia": 0,
            "candidato": None, "tentativas": 0, "proxima": 0.0,
            "travado": False})

    # ---------- consulta ----------
    def nome(self, pid):
        e = self._d.get(pid)
        return e["nome"] if e and e["travado"] else None

    def semelhanca(self, pid):
        e = self._d.get(pid)
        return e["sim"] if e else 0.0

    def conhecido(self, pid):
        return self.nome(pid) is not None

    def rotulo(self, pid):
        return self.nome(pid) or f"Pessoa · ID {pid}"

    # ---------- reconhecimento ----------
    def precisa_tentar(self, pid, agora):
        e = self._estado(pid)
        if e["travado"] or e["tentativas"] >= self.max_tentativas:
            return False
        return agora >= e["proxima"]

    def registrar(self, pid, nome, sim, agora):
        """Anota o resultado de uma tentativa (nome=None se desconhecido)."""
        e = self._estado(pid)
        e["tentativas"] += 1
        e["proxima"] = agora + self.intervalo_s
        e["sim"] = sim
        if nome is not None and nome == e["candidato"]:
            e["sequencia"] += 1
        else:
            e["candidato"], e["sequencia"] = nome, (1 if nome else 0)
        if nome is not None and e["sequencia"] >= self.votos:
            e["nome"], e["travado"] = nome, True
        return e["travado"]

    def definir(self, pid, nome, sim=1.0):
        """Fixa a identidade (usado logo depois de um cadastro)."""
        e = self._estado(pid)
        e.update(nome=nome, sim=sim, travado=True, candidato=nome,
                 sequencia=self.votos)

    def esquecer_ausentes(self, ids_vivos):
        for pid in [p for p in self._d if p not in ids_vivos]:
            del self._d[pid]

    def reiniciar(self):
        self._d.clear()
