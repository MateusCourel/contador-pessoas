"""Fluxo do cadastro (máquina de estados, sem câmera e sem desenho).

ESPERA -> AVISO -> CALIBRAR -> POSES -> NOME -> FIM -> ESPERA

Quem usa (o núcleo) a cada quadro chama  passo(frame, pontos, agora)  e
repassa os toques do monitor com  aceitar() / cancelar() / tocar_teclado().
Para mostrar na TV e no monitor touch, basta ler as propriedades de
"visão": titulo, subtitulo, progresso, aviso, poses_feitas.

Se ninguém mexer por um tempo, o cadastro é cancelado sozinho, para o
quiosque nunca ficar preso numa tela de cadastro abandonada.
"""
from embeddings import LARGURA_MINIMA
from poses import (POSES, CalibradorDeFrente, GuiaDePoses, Suavizador,
                   classificar_pose, razoes_da_cabeca)
from teclado import TecladoVirtual

ESPERA, AVISO, CALIBRAR, POSES_, NOME, FIM = range(6)
NOMES_DOS_ESTADOS = ("ESPERA", "AVISO", "CALIBRAR", "POSES", "NOME", "FIM")

ROTULOS = {"centro": "FRENTE", "esquerda": "ESQUERDA", "direita": "DIREITA",
           "cima": "CIMA", "baixo": "BAIXO"}
INSTRUCOES = {
    "centro": "OLHE DE FRENTE",
    "esquerda": "VIRE A CABEÇA PARA A ESQUERDA",
    "direita": "VIRE A CABEÇA PARA A DIREITA",
    "cima": "OLHE PARA CIMA",
    "baixo": "OLHE PARA BAIXO",
}

PREPARO_S = 1.5
LIMITE_AVISO_S = 45.0       # parado no aviso de privacidade
LIMITE_SEM_ROSTO_S = 20.0   # calibrando/posando sem aparecer rosto
LIMITE_NOME_S = 90.0        # sem tocar no teclado


def largura_do_rosto(pontos, largura_img):
    if not pontos:
        return 0
    xs = [p[0] for p in pontos]
    return int(round((max(xs) - min(xs)) * largura_img))


class FluxoDeCadastro:
    def __init__(self, banco, extrair, teclado=None, fim_s=3.0):
        """banco: Banco. extrair(frame, pontos) -> embedding ou None."""
        self.banco = banco
        self.extrair = extrair
        self.teclado = teclado or TecladoVirtual(1280, 800)
        self.fim_s = fim_s
        self.estado = ESPERA
        self._calibrador = CalibradorDeFrente(amostras=20, exigir_estavel=True)
        self._suavizador = Suavizador(alpha=0.5)
        self._guia = GuiaDePoses()
        self._capturas = {}
        self._inicio_estado = 0.0
        self._ultima_atividade = 0.0
        self._ultimo_rosto = 0.0
        self._progresso = 0.0
        self._aviso, self._aviso_ate = "", 0.0
        self._largura_rosto = 0
        self._sem_rosto = False
        self.nome = ""
        self._cadastrado = None

    # ---------- consulta ----------
    @property
    def ativo(self):
        return self.estado != ESPERA

    @property
    def nome_do_estado(self):
        return NOMES_DOS_ESTADOS[self.estado]

    @property
    def progresso(self):
        return self._progresso

    @property
    def poses_feitas(self):
        return list(self._capturas)

    @property
    def pose_atual(self):
        return self._guia.passo_atual if self.estado == POSES_ else None

    def aviso(self, agora):
        return self._aviso if agora < self._aviso_ate else ""

    def pop_cadastrado(self):
        """Nome recém-cadastrado (uma vez só) ou None."""
        nome, self._cadastrado = self._cadastrado, None
        return nome

    @property
    def titulo(self):
        e = self.estado
        if e == AVISO:
            return "AVISO DE PRIVACIDADE"
        if e == CALIBRAR:
            return ("OLHE PARA A CÂMERA..." if self._preparando
                    else "FIQUE PARADO, OLHANDO DE FRENTE")
        if e == POSES_:
            return INSTRUCOES.get(self._guia.passo_atual, "QUASE LÁ...")
        if e == NOME:
            return "DIGITE SEU NOME"
        if e == FIM:
            return "CADASTRADO!"
        return ""

    @property
    def subtitulo(self):
        e = self.estado
        if e == AVISO:
            return "Guardamos só números do rosto, nunca fotos · confirme no monitor touch"
        if e in (CALIBRAR, POSES_):
            if self._sem_rosto:
                return "nenhum rosto encontrado: fique de frente para a câmera"
            if 0 < self._largura_rosto < LARGURA_MINIMA:
                return "rosto pequeno: chegue um pouco mais perto"
            if e == POSES_:
                total = len(self._guia.passos)
                return f"pose {min(self._guia.indice + 1, total)} de {total}"
            return "vamos aprender como é o seu rosto de frente"
        if e == NOME:
            return "use o teclado do monitor touch"
        if e == FIM:
            return self.nome
        return ""

    # ---------- controle ----------
    def iniciar(self, agora):
        if self.estado != ESPERA:
            return False
        self._resetar_internos()
        self.estado = AVISO
        self._inicio_estado = self._ultima_atividade = agora
        return True

    def aceitar(self, agora):
        if self.estado == AVISO:
            self.estado = CALIBRAR
            self._inicio_estado = self._ultimo_rosto = agora
            self._ultima_atividade = agora

    def cancelar(self, motivo="CADASTRO CANCELADO", agora=0.0):
        if self.estado == ESPERA:
            return
        self._resetar_internos()
        self.estado = ESPERA
        self._aviso, self._aviso_ate = motivo, agora + 3.0

    def _resetar_internos(self):
        self._calibrador.reiniciar()
        self._suavizador.reiniciar()
        self._guia.reiniciar()
        self._capturas = {}
        self._progresso = 0.0
        self._largura_rosto = 0
        self._sem_rosto = False
        self.nome = ""
        self.teclado.reiniciar()

    @property
    def _preparando(self):
        return self._agora_ref - self._inicio_estado < PREPARO_S

    _agora_ref = 0.0

    # ---------- teclado (nome) ----------
    def tocar_teclado(self, x, y, agora):
        if self.estado != NOME:
            return
        self._ultima_atividade = agora
        self._tratar_acao(self.teclado.tocar(x, y), agora)

    def tecla_fisica(self, tecla, agora):
        """Teclado do computador: ENTER=OK, BACKSPACE, caracteres."""
        if self.estado != NOME:
            return
        self._ultima_atividade = agora
        if tecla in (13, 10):
            self._tratar_acao("ok", agora)
        elif tecla in (8, 127):
            self.teclado.apagar()
        elif 32 <= tecla < 127:
            self.teclado.digitar_tecla(chr(tecla))

    def _tratar_acao(self, acao, agora):
        if acao == "cancelar":
            self.cancelar(agora=agora)
        elif acao == "ok":
            candidato = self.teclado.texto.strip()
            if not candidato:
                self._avisar("DIGITE UM NOME", agora)
            elif self.banco.existe_nome(candidato):
                self._avisar("JÁ EXISTE ESSE NOME", agora)
            else:
                self.banco.cadastrar(candidato, dict(self._capturas))
                self.nome = candidato
                self._cadastrado = candidato
                self.estado = FIM
                self._inicio_estado = agora

    def _avisar(self, msg, agora, segundos=3.0):
        self._aviso, self._aviso_ate = msg, agora + segundos

    # ---------- a cada quadro ----------
    def passo(self, frame, pontos, agora):
        """frame: quadro da câmera. pontos: malha do rosto de quem está se
        cadastrando (ou None)."""
        self._agora_ref = agora
        e = self.estado
        if e == ESPERA:
            return
        if e == AVISO:
            if agora - self._ultima_atividade > LIMITE_AVISO_S:
                self.cancelar("TEMPO ESGOTADO", agora)
            return
        if e == NOME:
            if agora - self._ultima_atividade > LIMITE_NOME_S:
                self.cancelar("TEMPO ESGOTADO", agora)
            return
        if e == FIM:
            if agora - self._inicio_estado >= self.fim_s:
                self._resetar_internos()
                self.estado = ESPERA
            return

        # CALIBRAR e POSES precisam do rosto
        largura = frame.shape[1] if frame is not None else 1
        self._largura_rosto = largura_do_rosto(pontos, largura)
        r = razoes_da_cabeca(pontos)
        self._sem_rosto = r is None
        if r is not None:
            self._ultimo_rosto = agora
        elif agora - self._ultimo_rosto > LIMITE_SEM_ROSTO_S:
            self.cancelar("TEMPO ESGOTADO", agora)
            return

        if e == CALIBRAR:
            if not self._preparando:
                yaw, pitch = self._suavizador.atualizar(*(r or (None, None)))
                self._calibrador.adicionar(yaw, pitch)
                self._progresso = self._calibrador.progresso
            else:
                self._progresso = 0.0
            if self._calibrador.pronto:
                self.estado = POSES_
                self._progresso = 0.0
            return

        # POSES
        yaw, pitch = self._suavizador.atualizar(*(r or (None, None)))
        pose = classificar_pose(yaw, pitch, self._calibrador.base_yaw,
                                self._calibrador.base_pitch)
        progresso, confirmou = self._guia.update(pose, agora)
        self._progresso = progresso
        if confirmou:
            pose_confirmada = self._guia.passos[self._guia.indice - 1]
            emb = (self.extrair(frame, pontos)
                   if pontos and self._largura_rosto >= LARGURA_MINIMA
                   else None)
            if emb is None:
                self._guia.indice -= 1                  # refaz só esta pose
                self._avisar("ROSTO PEQUENO: CHEGUE MAIS PERTO", agora, 2.0)
            else:
                self._capturas[pose_confirmada] = emb
        if self._guia.concluido:
            self.estado = NOME
            self._inicio_estado = self._ultima_atividade = agora
            self.teclado.reiniciar()
            self._progresso = 0.0
