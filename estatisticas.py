"""Estatísticas e dados do sistema para o painel da TV.

- HistoricoPorMinuto: quantas pessoas entraram em cada um dos últimos minutos.
- MediaMovel: suaviza números que oscilam (FPS, latência).
- RegistroDeEventos: anota cada entrada/saída num CSV (dados/eventos.csv),
  sem nenhum dado pessoal, só hora, evento e o número temporário do rastreio.
- Leitura de temperatura, CPU e RAM do Raspberry Pi.
- Configuração salva (dados/config.json): posição da linha, sentido etc.
"""
import json
import os
import time
from datetime import datetime

PASTA_DADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "dados")


class HistoricoPorMinuto:
    def __init__(self, minutos=30):
        self.minutos = minutos
        self._baldes = {}            # minuto (inteiro) -> entradas

    def registrar(self, agora=None, quantidade=1):
        agora = time.time() if agora is None else agora
        minuto = int(agora // 60)
        self._baldes[minuto] = self._baldes.get(minuto, 0) + quantidade
        antigos = [m for m in self._baldes if m <= minuto - self.minutos]
        for m in antigos:
            del self._baldes[m]

    def serie(self, agora=None):
        """Lista (do mais antigo ao minuto atual) com `minutos` valores."""
        agora = time.time() if agora is None else agora
        atual = int(agora // 60)
        return [self._baldes.get(m, 0)
                for m in range(atual - self.minutos + 1, atual + 1)]

    def reiniciar(self):
        self._baldes.clear()


class MediaMovel:
    def __init__(self, alpha=0.1, inicial=0.0):
        self.alpha = alpha
        self.valor = inicial
        self._iniciada = inicial != 0.0

    def somar(self, x):
        if not self._iniciada:
            self.valor, self._iniciada = float(x), True
        else:
            self.valor += self.alpha * (x - self.valor)
        return self.valor


class RegistroDeEventos:
    """Acrescenta linhas ao CSV de eventos (cria o arquivo e a pasta)."""

    def __init__(self, caminho=None):
        self.caminho = caminho or os.path.join(PASTA_DADOS, "eventos.csv")

    def escrever(self, evento, pessoa_id):
        try:
            os.makedirs(os.path.dirname(self.caminho), exist_ok=True)
            novo = not os.path.exists(self.caminho)
            with open(self.caminho, "a", encoding="utf-8") as arq:
                if novo:
                    arq.write("momento,evento,id_rastreio\n")
                arq.write(f"{datetime.now().isoformat(timespec='seconds')},"
                          f"{evento},{pessoa_id}\n")
        except OSError as erro:                  # nunca derruba o programa
            print(f"[eventos] não consegui gravar: {erro}")


# ---------- leitura do sistema ----------
def ler_temperatura(caminho="/sys/class/thermal/thermal_zone0/temp"):
    try:
        with open(caminho) as arq:
            return int(arq.read().strip()) / 1000.0
    except (OSError, ValueError):
        return 0.0


def calcular_ram(texto_meminfo):
    """Percentual de RAM em uso, a partir do texto de /proc/meminfo."""
    valores = {}
    for linha in texto_meminfo.splitlines():
        partes = linha.replace(":", " ").split()
        if len(partes) >= 2 and partes[1].isdigit():
            valores[partes[0]] = int(partes[1])
    total, livre = valores.get("MemTotal", 0), valores.get("MemAvailable")
    if not total or livre is None:
        return 0.0
    return 100.0 * (total - livre) / total


def ler_ram(caminho="/proc/meminfo"):
    try:
        with open(caminho) as arq:
            return calcular_ram(arq.read())
    except OSError:
        return 0.0


def calcular_cpu(antes, depois):
    """Percentual de uso entre duas leituras (total, ocioso) de /proc/stat."""
    total = depois[0] - antes[0]
    ocioso = depois[1] - antes[1]
    if total <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (total - ocioso) / total))


def _ler_cpu(caminho="/proc/stat"):
    try:
        with open(caminho) as arq:
            nums = [int(x) for x in arq.readline().split()[1:]]
    except (OSError, ValueError):
        return None
    ocioso = nums[3] + (nums[4] if len(nums) > 4 else 0)   # idle + iowait
    return sum(nums), ocioso


class MedidorDeCpu:
    def __init__(self):
        self._antes = _ler_cpu()

    def percentual(self):
        agora = _ler_cpu()
        if agora is None or self._antes is None:
            return 0.0
        valor = calcular_cpu(self._antes, agora)
        self._antes = agora
        return valor


def formatar_hora(agora=None):
    return time.strftime("%H:%M", time.localtime(agora))


# ---------- configuração salva ----------
class Configuracao:
    """Pequeno arquivo JSON com os ajustes feitos no monitor touch."""

    def __init__(self, caminho=None):
        self.caminho = caminho or os.path.join(PASTA_DADOS, "config.json")
        self.valores = {}
        try:
            with open(self.caminho, encoding="utf-8") as arq:
                lido = json.load(arq)
            if isinstance(lido, dict):
                self.valores = lido
        except (OSError, ValueError):
            pass

    def obter(self, chave, padrao=None):
        return self.valores.get(chave, padrao)

    def definir(self, **novos):
        self.valores.update(novos)
        try:
            os.makedirs(os.path.dirname(self.caminho), exist_ok=True)
            with open(self.caminho, "w", encoding="utf-8") as arq:
                json.dump(self.valores, arq, indent=2)
        except OSError as erro:
            print(f"[config] não consegui salvar: {erro}")
