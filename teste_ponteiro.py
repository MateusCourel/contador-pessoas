"""Teste do mouse virtual: olhe o cursor do mouse nas duas telas.

O cursor vai para a TV (borda direita), fica 4 s, volta para o monitor
touch (borda esquerda), fica 4 s; repete 3 vezes. Se o cursor se mexer, o
ponteiro virtual está funcionando.

Rodar:  python teste_ponteiro.py
"""
import time

from ponteiro import Ponteiro


def main():
    p = Ponteiro()
    if not p.disponivel:
        print("Ponteiro virtual indisponível:", p.erro)
        return
    for i in range(3):
        print(f"{i + 1}/3  cursor -> TV")
        p.ir_para_direita()
        time.sleep(4)
        print(f"{i + 1}/3  cursor -> monitor touch")
        p.ir_para_esquerda()
        time.sleep(4)
    p.fechar()
    print("Fim. O cursor foi visto nas duas telas? (sim/não)")


if __name__ == "__main__":
    main()
