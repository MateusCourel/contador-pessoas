"""Organiza as duas telas ao abrir o programa, em qualquer porta HDMI.

Problema: o wayfire.ini fixa  HDMI-A-1 = touch  e  HDMI-A-2 = TV. Se a TV
for ligada na outra porta (ou o Pi ligar com a TV desligada), o Wayfire usa o
modo "preferido" (a TV vira 3840x2160 em 0,0) e as janelas caem na tela errada.

Aqui a gente identifica cada tela pelo que ela É, não pela porta:
  - touch = a que tem o modo 1280x800
  - TV    = a outra (forçada a 1920x1080 a 60 Hz: 4K pesa à toa)
e manda o wlr-randr colocar o touch em 0,0 e a TV em 1280,0. O toque do
monitor (TSTP MTouch) também é ligado à saída certa no wayfire.ini.
"""
import os
import re
import shutil
import subprocess
import time

TOUCH_MODO = (1280, 800)
TV_MODO = (1920, 1080)
POS_TOUCH, POS_TV = (0, 0), (1280, 0)

_CABECALHO = re.compile(r'^(\S+) "(.*)"')
_MODO = re.compile(r'^\s+(\d+)x(\d+) px, ([\d.]+) Hz(.*)')
_POS = re.compile(r'^\s+Position: (-?\d+),(-?\d+)')


def interpretar_wlr_randr(texto):
    """Lê a saída do `wlr-randr` e devolve a lista de saídas:
    [{"nome", "descricao", "modos": [(w, h, hz)], "atual": (w, h) ou None,
      "pos": (x, y), "ligada": bool}]"""
    saidas = []
    for linha in texto.splitlines():
        m = _CABECALHO.match(linha)
        if m:
            saidas.append({"nome": m.group(1), "descricao": m.group(2),
                           "modos": [], "atual": None, "pos": (0, 0),
                           "ligada": True})
            continue
        if not saidas:
            continue
        atual = saidas[-1]
        m = _MODO.match(linha)
        if m:
            w, h, hz = int(m.group(1)), int(m.group(2)), float(m.group(3))
            atual["modos"].append((w, h, hz))
            if "current" in m.group(4):
                atual["atual"] = (w, h)
            continue
        m = _POS.match(linha)
        if m:
            atual["pos"] = (int(m.group(1)), int(m.group(2)))
        elif "Enabled: no" in linha:
            atual["ligada"] = False
    return saidas


def escolher(saidas):
    """Devolve (touch, tv) como dicts, ou (None, None) se não há duas telas
    ligadas ou não dá para distinguir."""
    ligadas = [s for s in saidas if s["ligada"]]
    if len(ligadas) < 2:
        return None, None
    com_touch = [s for s in ligadas
                 if any((w, h) == TOUCH_MODO for w, h, _ in s["modos"])]
    # se as duas têm 1280x800, o touch é a que NÃO tem 1920x1080 preferido
    # de TV: na dúvida, a de menos modos grandes
    if not com_touch:
        return None, None
    touch = min(com_touch,
                key=lambda s: sum(1 for w, h, _ in s["modos"] if w >= 2560))
    tv = next((s for s in ligadas if s is not touch), None)
    return touch, tv


def _refresh_60(modos, tamanho):
    """O modo `tamanho` mais perto de 60 Hz (devolve o texto do wlr-randr)."""
    candidatos = [hz for w, h, hz in modos if (w, h) == tamanho]
    if not candidatos:
        return None
    hz = min(candidatos, key=lambda x: abs(x - 60.0))
    return f"{tamanho[0]}x{tamanho[1]}@{hz:.3f}Hz"


def planejar(saidas):
    """Lista de argumentos do wlr-randr para deixar o layout certo, ou []
    se já está certo (ou não há o que fazer)."""
    touch, tv = escolher(saidas)
    if touch is None or tv is None:
        return []
    certo = (touch["atual"] == TOUCH_MODO and touch["pos"] == POS_TOUCH and
             tv["atual"] == TV_MODO and tv["pos"] == POS_TV)
    if certo:
        return []
    modo_touch = _refresh_60(touch["modos"], TOUCH_MODO)
    modo_tv = _refresh_60(tv["modos"], TV_MODO)
    args = ["--output", touch["nome"]]
    if modo_touch:
        args += ["--mode", modo_touch]
    args += ["--pos", f"{POS_TOUCH[0]},{POS_TOUCH[1]}",
             "--output", tv["nome"]]
    if modo_tv:
        args += ["--mode", modo_tv]
    args += ["--pos", f"{POS_TV[0]},{POS_TV[1]}"]
    return args


def ini_corrigido(texto, touch, tv):
    """Devolve o texto do wayfire.ini com as seções das saídas e do toque
    (TSTP MTouch) apontando para `touch` e `tv`. Mantém o resto."""
    blocos, atual = [], []
    for linha in texto.splitlines():
        if linha.startswith("["):
            if atual:
                blocos.append(atual)
            atual = [linha]
        else:
            atual.append(linha)
    if atual:
        blocos.append(atual)

    def apagar(bloco):
        t = bloco[0].strip()
        return (t.startswith("[output:HDMI") or
                t == "[input-device:TSTP MTouch]")

    # (blocos antes da 1ª seção, se houver, têm cabeçalho vazio: mantemos)
    mantidos = [b for b in blocos if not apagar(b)]
    while mantidos and not mantidos[-1][-1].strip():
        mantidos[-1].pop()
    novo = [
        "", "[input-device:TSTP MTouch]", f"output = {touch}",
        "", f"[output:{touch}]", "mode = 1280x800@60",
        f"position = {POS_TOUCH[0]},{POS_TOUCH[1]}",
        "", f"[output:{tv}]", "mode = 1920x1080@60",
        f"position = {POS_TV[0]},{POS_TV[1]}", ""]
    linhas = [l for b in mantidos for l in b]
    # remove linhas em branco repetidas no fim antes de acrescentar
    while linhas and not linhas[-1].strip():
        linhas.pop()
    return "\n".join(linhas + novo)


def organizar(log=print, esperar_s=2.5):
    """Confere as telas e arruma o que for preciso. Devolve True se mudou
    alguma coisa. Nunca levanta erro: se não der, o programa segue."""
    if not shutil.which("wlr-randr"):
        return False
    try:
        saida = subprocess.run(["wlr-randr"], capture_output=True, text=True,
                               timeout=8).stdout
        saidas = interpretar_wlr_randr(saida)
        touch, tv = escolher(saidas)
        if touch is None:
            return False
        mudou = False
        # toque do monitor ligado à saída certa (o Wayfire relê o arquivo)
        caminho = os.path.expanduser("~/.config/wayfire.ini")
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8") as f:
                velho = f.read()
            novo = ini_corrigido(velho, touch["nome"], tv["nome"])
            if novo.strip() != velho.strip():
                shutil.copy(caminho, caminho + ".bak")
                with open(caminho, "w", encoding="utf-8") as f:
                    f.write(novo + "\n")
                log(f"[telas] wayfire.ini ajustado: touch={touch['nome']}, "
                    f"TV={tv['nome']} (cópia em wayfire.ini.bak)")
                mudou = True
        args = planejar(saidas)
        if args:
            log(f"[telas] ajustando: wlr-randr {' '.join(args)}")
            subprocess.run(["wlr-randr"] + args, capture_output=True,
                           timeout=15)
            mudou = True
        if mudou:
            time.sleep(esperar_s)       # o XWayland leva um instante
        return mudou
    except Exception as erro:
        log(f"[telas] não consegui organizar as telas: {erro}")
        return False


if __name__ == "__main__":
    print("mudou algo:", organizar())
