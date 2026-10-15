"""ETAPA 4 - Cadastro completo de uma pessoa.

Fluxo:
  1) Mão aberta por 1 s            -> inicia
  2) Aviso de privacidade          -> S aceita, N cancela
  3) Olhar de frente (calibração)  -> aprende o "centro" do rosto
  4) 5 poses guiadas               -> a cada pose confirmada, tira o embedding
  5) Digitar o nome + ENTER        -> grava no banco (dados/pessoas.db)

Só os embeddings (números) são gravados. As fotos NÃO são guardadas.
(Na etapa 5 o nome passa a ser digitado num teclado virtual na tela touch;
por enquanto usa o teclado do computador, com a janela selecionada.)

Teclas: ESC cancela o cadastro em andamento, Q (fora da digitação) sai.
"""
import time

import cv2

from banco import Banco
from camera import Camera
from embeddings import ExtratorDeEmbedding
from gestos import (GESTO_MAO_ABERTA, DetectorDeGestos, GatilhoPorTempo,
                    desenhar_mao)
from poses import (CalibradorDeFrente, GuiaDePoses, classificar_pose,
                   razoes_da_cabeca)
from rosto import DetectorDeRosto, desenhar_rosto

ESPERA, AVISO, CALIBRAR, POSES, NOME, FIM = range(6)
ROTULOS = {"centro": "FRENTE", "esquerda": "ESQUERDA", "direita": "DIREITA",
           "cima": "CIMA", "baixo": "BAIXO"}
INSTRUCOES = {
    "centro": "OLHE DE FRENTE",
    "esquerda": "VIRE A CABECA PARA A ESQUERDA",
    "direita": "VIRE A CABECA PARA A DIREITA",
    "cima": "OLHE PARA CIMA",
    "baixo": "OLHE PARA BAIXO",
}
MAX_NOME = 30


def texto(frame, msg, pos, tamanho=1.0, cor=(0, 255, 0), espessura=2):
    cv2.putText(frame, msg, pos, cv2.FONT_HERSHEY_SIMPLEX, tamanho, cor,
                espessura, cv2.LINE_AA)


def barra(frame, progresso, cor=(0, 200, 0)):
    h, w = frame.shape[:2]
    x0, y0, largura, altura = 40, h - 60, w - 80, 24
    cv2.rectangle(frame, (x0, y0), (x0 + largura, y0 + altura),
                  (255, 255, 255), 2)
    if progresso > 0:
        cv2.rectangle(frame, (x0, y0),
                      (x0 + int(largura * progresso), y0 + altura), cor, -1)


def lista_de_poses(frame, guia):
    x = frame.shape[1] - 330
    for i, passo in enumerate(guia.passos):
        feito, atual = i < guia.indice, i == guia.indice
        cor = (0, 255, 0) if feito else ((0, 255, 255) if atual
                                         else (200, 200, 200))
        texto(frame, f"{'[x]' if feito else '[ ]'} {ROTULOS[passo]}",
              (x, 50 + i * 40), 0.9, cor)


def main():
    cam = Camera(largura=1280, altura=720, preferir="csi")
    gestos = DetectorDeGestos("gesture_recognizer.task")
    rosto = DetectorDeRosto("face_landmarker.task")
    extrator = ExtratorDeEmbedding("face_recognition_sface_2021dec.onnx")
    banco = Banco()

    estado = ESPERA
    gatilho = GatilhoPorTempo(segurar_s=1.0, recarga_s=2.0)
    calibrador = CalibradorDeFrente(amostras=30)
    guia = GuiaDePoses()
    capturas = {}
    nome = ""
    mensagem, mensagem_ate = "", 0.0

    def recomecar(aviso=""):
        nonlocal estado, capturas, nome, mensagem, mensagem_ate
        estado, capturas, nome = ESPERA, {}, ""
        calibrador.reiniciar()
        guia.reiniciar()
        if aviso:
            mensagem, mensagem_ate = aviso, time.monotonic() + 3.0

    try:
        while True:
            frame = cam.read()
            if frame is None:
                continue
            tecla = -1

            if estado == ESPERA:
                gesto, _ = gestos.detectar(frame)
                desenhar_mao(frame, gestos.pontos)
                progresso, disparou = gatilho.update(gesto == GESTO_MAO_ABERTA)
                texto(frame, "MOSTRE A MAO ABERTA PARA CADASTRAR", (40, 50),
                      1.1, (0, 255, 255), 3)
                texto(frame, f"{len(banco.listar())} pessoa(s) cadastrada(s)",
                      (40, 95), 0.8, (255, 255, 255))
                barra(frame, progresso)
                if disparou:
                    estado = AVISO

            elif estado == AVISO:
                texto(frame, "AVISO DE PRIVACIDADE", (40, 60), 1.3,
                      (0, 255, 255), 3)
                for i, linha in enumerate([
                        "Vamos guardar apenas NUMEROS do seu rosto",
                        "(nao guardamos as fotos), junto com seu nome,",
                        "para reconhecer voce. Voce pode pedir para",
                        "apagar seu cadastro a qualquer momento.",
                        "",
                        "S = aceito e continuar      N = cancelar"]):
                    texto(frame, linha, (40, 130 + i * 45), 0.95,
                          (255, 255, 255), 2)

            elif estado == CALIBRAR:
                pontos = rosto.detectar(frame)
                desenhar_rosto(frame, pontos)
                r = razoes_da_cabeca(pontos)
                calibrador.adicionar(*(r if r else (None, None)))
                texto(frame, "FIQUE PARADO, OLHANDO DE FRENTE", (40, 50),
                      1.1, (0, 255, 255), 3)
                if r is None:
                    texto(frame, "(nenhum rosto encontrado)", (40, 95), 0.9,
                          (0, 0, 255))
                barra(frame, calibrador.progresso, (0, 200, 255))
                if calibrador.pronto:
                    estado = POSES

            elif estado == POSES:
                pontos = rosto.detectar(frame)
                r = razoes_da_cabeca(pontos)
                yaw, pitch = r if r else (None, None)
                pose = classificar_pose(yaw, pitch, calibrador.base_yaw,
                                        calibrador.base_pitch)
                progresso, confirmou = guia.update(pose)
                if confirmou:
                    nome_da_pose = guia.passos[guia.indice - 1]
                    emb = extrator.extrair(frame, pontos)
                    if emb is None:
                        # rosto pequeno/perdido: refaz só esta pose
                        guia.indice -= 1
                        mensagem = "CHEGUE MAIS PERTO"
                        mensagem_ate = time.monotonic() + 2.0
                    else:
                        capturas[nome_da_pose] = emb
                        print(f">>> pose capturada: {ROTULOS[nome_da_pose]}")
                desenhar_rosto(frame, pontos)
                lista_de_poses(frame, guia)
                if guia.concluido:
                    estado = NOME
                else:
                    texto(frame, INSTRUCOES[guia.passo_atual], (40, 50), 1.1,
                          (0, 255, 255), 3)
                    barra(frame, progresso)

            elif estado == NOME:
                texto(frame, "DIGITE O NOME E APERTE ENTER", (40, 60), 1.2,
                      (0, 255, 255), 3)
                cv2.rectangle(frame, (40, 100), (frame.shape[1] - 40, 170),
                              (255, 255, 255), 2)
                texto(frame, nome + "_", (55, 150), 1.4, (255, 255, 255), 3)
                texto(frame, "(sem acentos por enquanto)  ESC cancela",
                      (40, 210), 0.8, (200, 200, 200))

            elif estado == FIM:
                texto(frame, f"CADASTRADO: {nome}", (40, 80), 1.5,
                      (0, 255, 0), 4)
                if time.monotonic() > mensagem_ate:
                    recomecar()

            if mensagem and time.monotonic() < mensagem_ate and \
                    estado != FIM:
                texto(frame, mensagem, (40, 130), 1.0, (0, 200, 255), 3)

            cv2.imshow("Etapa 4 - cadastro", frame)
            tecla = cv2.waitKey(1) & 0xFF

            if tecla == 27 and estado != ESPERA:        # ESC
                recomecar("CADASTRO CANCELADO")
            elif estado == AVISO:
                if tecla in (ord("s"), ord("S")):
                    estado = CALIBRAR
                elif tecla in (ord("n"), ord("N")):
                    recomecar("CADASTRO CANCELADO")
            elif estado == NOME and tecla != 255:
                if tecla in (13, 10):                   # ENTER
                    if nome.strip():
                        banco.cadastrar(nome, capturas)
                        print(f">>> {nome.strip()} cadastrado(a) com "
                              f"{len(capturas)} embeddings")
                        nome = nome.strip()
                        estado, mensagem_ate = FIM, time.monotonic() + 3.0
                elif tecla in (8, 127):                 # BACKSPACE
                    nome = nome[:-1]
                elif 32 <= tecla < 127 and len(nome) < MAX_NOME:
                    nome += chr(tecla)
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
