"""Mão do cadastro: só vale a mão de quem está na frente.

O gesto de "palma aberta" inicia o cadastro. Para não deixar uma pessoa lá
no fundo disparar o cadastro (nem gastar desenho à toa), só consideramos a
mão que está na região da pessoa mais próxima da câmera (a de maior caixa).
Lógica pura, com testes.
"""

MARGEM_X = 0.40      # a região da pessoa cresce 40% da largura para cada lado
MARGEM_Y = 0.20      # e 20% da altura para cima/baixo (braço levantado)


def area(caixa):
    return max(caixa[2] - caixa[0], 0.0) * max(caixa[3] - caixa[1], 0.0)


def pessoa_da_frente(pistas):
    """A pista visível com a maior caixa (a mais perto da câmera) ou None."""
    visiveis = [p for p in pistas if p.visivel]
    return max(visiveis, key=lambda p: area(p.caixa)) if visiveis else None


def regiao_da_pessoa(caixa, mx=MARGEM_X, my=MARGEM_Y):
    x0, y0, x1, y1 = caixa
    largura, altura = x1 - x0, y1 - y0
    return (x0 - mx * largura, y0 - my * altura,
            x1 + mx * largura, y1 + my * altura)


def centro_da_mao(pontos):
    """Centro da palma: média do pulso e das bases dos dedos."""
    chaves = (0, 5, 9, 13, 17)
    return (sum(pontos[i][0] for i in chaves) / len(chaves),
            sum(pontos[i][1] for i in chaves) / len(chaves))


def mao_da_pessoa(pontos, caixa):
    """True se o centro da mão cai na região da pessoa (caixa expandida)."""
    if not pontos or len(pontos) < 21 or caixa is None:
        return False
    cx, cy = centro_da_mao(pontos)
    x0, y0, x1, y1 = regiao_da_pessoa(caixa)
    return x0 <= cx <= x1 and y0 <= cy <= y1
