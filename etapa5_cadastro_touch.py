"""ETAPA 5 - Cadastro pela tela touch (com teclado virtual).

Igual à etapa 4, mas tudo pode ser feito com o dedo:
  1) Mão aberta por 1 s (ou toque em CADASTRAR) -> inicia
  2) Aviso de privacidade                       -> toque em ACEITO ou CANCELAR
  3) Olhar de frente, depois as 5 poses
  4) Digitar o nome no teclado da tela (com acentos) -> toque em OK
O teclado do computador também continua funcionando.

Só os embeddings (números) são gravados. As fotos NÃO são guardadas.

Rodar:
    python etapa5_cadastro_touch.py            tela cheia (para o monitor touch)
    python etapa5_cadastro_touch.py --janela   em janela (para testar)
Teclas: ESC cancela o cadastro, Q (na tela inicial) sai.
"""
import sys
import time

import cv2

from banco import Banco
from camera import Camera
from embeddings import ExtratorDeEmbedding
from etapa4_cadastro import (AVISO, CALIBRAR, ESPERA, FIM, INSTRUCOES, NOME,
                             POSES, ROTULOS, barra, lista_de_poses, texto)
from gestos import (GESTO_MAO_ABERTA, DetectorDeGestos, GatilhoPorTempo,
                    desenhar_mao)
from embeddings import LARGURA_MINIMA
from poses import (CalibradorDeFrente, GuiaDePoses, Suavizador,
                   classificar_pose, razoes_da_cabeca)
from rosto import DetectorDeRosto, desenhar_rosto
from teclado import TecladoVirtual

JANELA = "Cadastro"
PREPARO_S = 1.5      # tempo para se ajeitar de frente antes de calibrar


def largura_do_rosto(pontos, w):
    """Largura do rosto em pixels (para avisar quando está longe demais)."""
    if not pontos:
        return 0
    xs = [p[0] for p in pontos]
    return int((max(xs) - min(xs)) * w)
VERDE, VERMELHO = (60, 160, 60), (50, 50, 170)


def botao(frame, retangulo, rotulo, cor):
    """Desenha um botão grande (x0, y0, x1, y1) com o texto centralizado."""
    x0, y0, x1, y1 = retangulo
    cv2.rectangle(frame, (x0, y0), (x1, y1), cor, -1)
    cv2.rectangle(frame, (x0, y0), (x1, y1), (255, 255, 255), 2)
    (tw, th), _ = cv2.getTextSize(rotulo, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 3)
    cv2.putText(frame, rotulo, (x0 + (x1 - x0 - tw) // 2,
                                y0 + (y1 - y0 + th) // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3,
                cv2.LINE_AA)


def dentro(retangulo, x, y):
    x0, y0, x1, y1 = retangulo
    return x0 <= x <= x1 and y0 <= y <= y1


def main():
    em_janela = "--janela" in sys.argv

    toques = []

    def ao_clicar(evento, x, y, flags, param):
        if evento == cv2.EVENT_LBUTTONDOWN:
            toques.append((x, y))

    cam = Camera(largura=1280, altura=720, preferir="csi")
    gestos = DetectorDeGestos("gesture_recognizer.task")
    rosto = DetectorDeRosto("face_landmarker.task")
    extrator = ExtratorDeEmbedding("face_recognition_sface_2021dec.onnx")
    banco = Banco()

    cv2.namedWindow(JANELA, cv2.WINDOW_NORMAL)
    if em_janela:
        cv2.resizeWindow(JANELA, 1180, 664)     # cabe na tela de 1280x800
    else:
        cv2.setWindowProperty(JANELA, cv2.WND_PROP_FULLSCREEN,
                              cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(JANELA, ao_clicar)

    estado = ESPERA
    gatilho = GatilhoPorTempo(segurar_s=1.0, recarga_s=2.0)
    calibrador = CalibradorDeFrente(amostras=20, exigir_estavel=True)
    suavizador = Suavizador(alpha=0.5)
    inicio_calibracao = 0.0
    guia = GuiaDePoses()
    teclado = None
    capturas = {}
    nome = ""
    mensagem, mensagem_ate = "", 0.0
    pedir_ok = False                             # ENTER do teclado físico

    def avisar(msg, segundos=3.0):
        nonlocal mensagem, mensagem_ate
        mensagem, mensagem_ate = msg, time.monotonic() + segundos

    def recomecar(aviso=""):
        nonlocal estado, capturas, nome, pedir_ok
        estado, capturas, nome, pedir_ok = ESPERA, {}, "", False
        calibrador.reiniciar()
        suavizador.reiniciar()
        guia.reiniciar()
        if teclado:
            teclado.reiniciar()
        if aviso:
            avisar(aviso)

    try:
        while True:
            frame = cam.read()
            if frame is None:
                continue
            h, w = frame.shape[:2]
            if teclado is None:
                teclado = TecladoVirtual(w, h)
            clique = toques.pop(0) if toques else None
            toques.clear()                       # só vale o toque mais antigo
            tecla = -1

            # botões que aparecem em cada tela (x0, y0, x1, y1)
            b_iniciar = (w - 340, 20, w - 40, 110)
            b_aceito = (40, h - 190, w // 2 - 20, h - 70)
            b_recusa = (w // 2 + 20, h - 190, w - 40, h - 70)
            b_cancelar = (w - 340, h - 135, w - 40, h - 80)

            if estado == ESPERA:
                gesto, _ = gestos.detectar(frame)
                desenhar_mao(frame, gestos.pontos)
                progresso, disparou = gatilho.update(gesto == GESTO_MAO_ABERTA)
                texto(frame, "MOSTRE A MAO ABERTA", (40, 50), 1.1,
                      (0, 255, 255), 3)
                texto(frame, "OU TOQUE EM CADASTRAR", (40, 95), 0.9,
                      (0, 255, 255), 2)
                texto(frame, f"{len(banco.listar())} pessoa(s) cadastrada(s)",
                      (40, 140), 0.8, (255, 255, 255))
                botao(frame, b_iniciar, "CADASTRAR", VERDE)
                barra(frame, progresso)
                if disparou or (clique and dentro(b_iniciar, *clique)):
                    estado = AVISO

            elif estado == AVISO:
                texto(frame, "AVISO DE PRIVACIDADE", (40, 60), 1.3,
                      (0, 255, 255), 3)
                for i, linha in enumerate([
                        "Vamos guardar apenas NUMEROS do seu rosto",
                        "(nao guardamos as fotos), junto com seu nome,",
                        "para reconhecer voce. Voce pode pedir para",
                        "apagar seu cadastro a qualquer momento."]):
                    texto(frame, linha, (40, 130 + i * 50), 1.0,
                          (255, 255, 255), 2)
                botao(frame, b_aceito, "ACEITO", VERDE)
                botao(frame, b_recusa, "CANCELAR", VERMELHO)
                if clique and dentro(b_aceito, *clique):
                    estado, inicio_calibracao = CALIBRAR, time.monotonic()
                elif clique and dentro(b_recusa, *clique):
                    recomecar("CADASTRO CANCELADO")

            elif estado == CALIBRAR:
                pontos = rosto.detectar(frame)
                desenhar_rosto(frame, pontos)
                r = razoes_da_cabeca(pontos)
                preparando = time.monotonic() - inicio_calibracao < PREPARO_S
                if not preparando:
                    yaw_s, pitch_s = suavizador.atualizar(*(r or (None, None)))
                    calibrador.adicionar(yaw_s, pitch_s)
                if preparando:
                    texto(frame, "OLHE PARA A CAMERA...", (40, 50), 1.1,
                          (0, 255, 255), 3)
                else:
                    texto(frame, "FIQUE PARADO, OLHANDO DE FRENTE", (40, 50),
                          1.1, (0, 255, 255), 3)
                if r is None and not preparando:
                    texto(frame, "(nenhum rosto encontrado)", (40, 95), 0.9,
                          (0, 0, 255))
                elif largura_do_rosto(pontos, w) < LARGURA_MINIMA:
                    texto(frame, "ROSTO PEQUENO: CHEGUE UM POUCO MAIS PERTO",
                          (40, 95), 0.9, (0, 0, 255))
                barra(frame, 0.0 if preparando else calibrador.progresso,
                      (0, 200, 255))
                botao(frame, b_cancelar, "CANCELAR", VERMELHO)
                if clique and dentro(b_cancelar, *clique):
                    recomecar("CADASTRO CANCELADO")
                elif calibrador.pronto:
                    estado = POSES

            elif estado == POSES:
                pontos = rosto.detectar(frame)
                r = razoes_da_cabeca(pontos)
                yaw, pitch = suavizador.atualizar(*(r or (None, None)))
                pose = classificar_pose(yaw, pitch, calibrador.base_yaw,
                                        calibrador.base_pitch)
                progresso, confirmou = guia.update(pose)
                if confirmou:
                    nome_da_pose = guia.passos[guia.indice - 1]
                    emb = extrator.extrair(frame, pontos)
                    if emb is None:
                        guia.indice -= 1         # refaz só esta pose
                        avisar(f"ROSTO PEQUENO ({largura_do_rosto(pontos, w)}"
                               f" px): CHEGUE MAIS PERTO", 2.0)
                    else:
                        capturas[nome_da_pose] = emb
                        print(f">>> pose capturada: {ROTULOS[nome_da_pose]}")
                desenhar_rosto(frame, pontos)
                lista_de_poses(frame, guia)
                if guia.concluido:
                    estado = NOME
                    teclado.reiniciar()
                else:
                    texto(frame, INSTRUCOES[guia.passo_atual], (40, 50), 1.1,
                          (0, 255, 255), 3)
                    barra(frame, progresso)
                    # leitura ao vivo: ajuda a entender por que uma pose não
                    # confirma (pose lida x pose pedida)
                    texto(frame, f"lido: {pose or 'sem rosto'}   "
                          f"rosto: {largura_do_rosto(pontos, w)} px",
                          (40, h - 80), 0.7, (255, 255, 255), 2)
                    botao(frame, b_cancelar, "CANCELAR", VERMELHO)
                    if clique and dentro(b_cancelar, *clique):
                        recomecar("CADASTRO CANCELADO")

            elif estado == NOME:
                teclado.desenhar(frame, "DIGITE O NOME E TOQUE EM OK")
                resultado = teclado.tocar(*clique) if clique else None
                if pedir_ok:
                    resultado, pedir_ok = "ok", False
                if resultado == "cancelar":
                    recomecar("CADASTRO CANCELADO")
                elif resultado == "ok":
                    candidato = teclado.texto.strip()
                    if not candidato:
                        avisar("DIGITE UM NOME", 2.0)
                    elif banco.existe_nome(candidato):
                        avisar("JA EXISTE ESSE NOME", 3.0)
                    else:
                        banco.cadastrar(candidato, capturas)
                        print(f">>> {candidato} cadastrado(a) com "
                              f"{len(capturas)} embeddings")
                        nome = candidato
                        estado = FIM
                        avisar("", 3.0)

            elif estado == FIM:
                texto(frame, f"CADASTRADO: {nome}", (40, 80), 1.5,
                      (0, 255, 0), 4)
                if time.monotonic() > mensagem_ate:
                    recomecar()

            if mensagem and time.monotonic() < mensagem_ate and \
                    estado != FIM:
                posicao = (w - 520, 60) if estado == NOME else (40, 140)
                texto(frame, mensagem, posicao, 1.0, (0, 200, 255), 3)

            cv2.imshow(JANELA, frame)
            tecla = cv2.waitKey(1) & 0xFF

            if tecla == 27 and estado != ESPERA:         # ESC
                recomecar("CADASTRO CANCELADO")
            elif estado == AVISO:
                if tecla in (ord("s"), ord("S")):
                    estado, inicio_calibracao = CALIBRAR, time.monotonic()
                elif tecla in (ord("n"), ord("N")):
                    recomecar("CADASTRO CANCELADO")
            elif estado == NOME and tecla != 255:
                if tecla in (13, 10):                    # ENTER = OK
                    pedir_ok = True
                elif tecla in (8, 127):                  # BACKSPACE
                    teclado.apagar()
                elif 32 <= tecla < 127:
                    teclado.digitar_tecla(chr(tecla))
            elif estado == ESPERA and tecla in (ord("q"), ord("Q")):
                break
    finally:
        rosto.fechar()
        gestos.fechar()
        banco.fechar()
        cam.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
