"""Configura o Wayfire para cada janela abrir na tela certa (uma vez só).

Problema: o OpenCV abre as janelas "TV" e "TOUCH" e o Wayfire (gerenciador de
janelas do Raspberry Pi OS) decide sozinho em qual monitor cada uma cai. Aqui
criamos regras no ~/.config/wayfire.ini:
    janela "TV"    -> monitor da TV (1920x1080)
    janela "TOUCH" -> monitor touch de 8" (1280x800)

Rodar (com as duas telas ligadas):
    DISPLAY=:0 python configurar_telas.py            mostra o que vai mudar
    DISPLAY=:0 python configurar_telas.py --aplicar  grava (faz cópia antes)
    DISPLAY=:0 python configurar_telas.py --desfazer volta ao arquivo original
Depois: sudo reboot
"""
import os
import re
import shutil
import sys

from telas import escolher_telas, listar_telas

ARQUIVO = os.path.expanduser("~/.config/wayfire.ini")
COPIA = ARQUIVO + ".bak-contador"
DRM = "/sys/class/drm"
MARCA = "# contador-pessoas"


def conectores(drm=DRM):
    """{nome_do_conector: 'LARGURAxALTURA'} das saídas HDMI conectadas, pela
    primeira resolução (a preferida) de cada uma."""
    achados = {}
    try:
        pastas = sorted(os.listdir(drm))
    except OSError:
        return achados
    for pasta in pastas:
        m = re.match(r"card\d+-(HDMI-A-\d+)$", pasta)
        if not m:
            continue
        base = os.path.join(drm, pasta)
        try:
            if open(os.path.join(base, "status")).read().strip() != "connected":
                continue
            achados[m.group(1)] = open(
                os.path.join(base, "modes")).readline().strip()
        except OSError:
            continue
    return achados


def regras(tv, touch, nome_tv, nome_touch):
    """Linhas [window-rules] para as duas janelas. tv/touch: dicts de telas.py
    (x, y, largura, altura); nome_*: conector (ex. 'HDMI-A-2') ou None."""
    def uma(chave, titulo, tela, conector):
        linhas = [f'{chave}_pos = on created if title is "{titulo}" then '
                  f'set geometry {tela["x"]} {tela["y"]} '
                  f'{tela["largura"]} {tela["altura"]}']
        if conector:
            linhas.append(f'{chave}_saida = on created if title is '
                          f'"{titulo}" then start_on_output "{conector}"')
        return linhas
    return uma("tv", "TV", tv, nome_tv) + \
        uma("touch", "TOUCH", touch, nome_touch)


def ajustar(texto, linhas_de_regra):
    """Devolve o texto do wayfire.ini com as regras e o plugin
    window-rules garantidos. Idempotente: rodar de novo não duplica."""
    linhas = [l for l in texto.splitlines()]
    # 1) plugin ligado
    for i, l in enumerate(linhas):
        if re.match(r"\s*plugins\s*=", l):
            if "window-rules" not in l.split("=", 1)[1].split():
                linhas[i] = l.rstrip() + " window-rules"
            break
    # 2) tira regras antigas nossas (para atualizar)
    limpas, dentro = [], False
    for l in linhas:
        if l.strip().startswith("[") and l.strip().endswith("]"):
            dentro = l.strip() == "[window-rules]"
        if dentro and re.match(r"\s*(tv|touch)_(pos|saida)\s*=", l):
            continue
        limpas.append(l)
    linhas = limpas
    # 3) coloca as regras na seção (cria se não existir)
    if "[window-rules]" in [l.strip() for l in linhas]:
        i = [l.strip() for l in linhas].index("[window-rules]")
        linhas[i + 1:i + 1] = linhas_de_regra
    else:
        if linhas and linhas[-1].strip():
            linhas.append("")
        linhas += [MARCA, "[window-rules]"] + linhas_de_regra
    return "\n".join(linhas) + "\n"


def main():
    desfazer, aplicar = "--desfazer" in sys.argv, "--aplicar" in sys.argv
    if desfazer:
        if os.path.exists(COPIA):
            shutil.copyfile(COPIA, ARQUIVO)
            print(f"Voltei {ARQUIVO} ao que era antes. Reinicie (sudo reboot).")
        else:
            print("Não há cópia salva; nada a desfazer.")
        return
    telas = listar_telas()
    tv, touch = escolher_telas(telas)
    if tv is None or tv is touch:
        print("Não encontrei duas telas ligadas. Rode com DISPLAY=:0 e com "
              "a TV e o monitor touch ligados.")
        return
    mapa = conectores()
    nome_touch = next((n for n, m in mapa.items() if m == "1280x800"), None)
    nome_tv = next((n for n, m in mapa.items()
                    if m == "1920x1080" and n != nome_touch), None)
    print(f"TV    : {tv['largura']}x{tv['altura']} em ({tv['x']},{tv['y']})"
          f"  saída {nome_tv or '?'}")
    print(f"TOUCH : {touch['largura']}x{touch['altura']} em "
          f"({touch['x']},{touch['y']})  saída {nome_touch or '?'}")
    novas = regras(tv, touch, nome_tv, nome_touch)
    try:
        original = open(ARQUIVO, encoding="utf-8").read()
    except OSError:
        original = ""
    novo = ajustar(original, novas)
    print("\nRegras que serão gravadas em [window-rules]:")
    print("\n".join("  " + l for l in novas))
    if not aplicar:
        print("\nNada foi gravado. Para gravar: python configurar_telas.py "
              "--aplicar")
        return
    if not os.path.exists(COPIA) and os.path.exists(ARQUIVO):
        shutil.copyfile(ARQUIVO, COPIA)
    with open(ARQUIVO, "w", encoding="utf-8") as arq:
        arq.write(novo)
    print(f"\nGravado em {ARQUIVO} (cópia em {COPIA}). Agora: sudo reboot")


if __name__ == "__main__":
    main()
