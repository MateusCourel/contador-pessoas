"""Núcleo: junta tudo, quadro a quadro (sem câmera nem janelas, é testável).

    nucleo.passo(frame, agora, deteccoes=None, toque=None, tecla=None)
        -> (imagem_da_TV 1920x1080, imagem_do_touch 1280x800)

Quem chama (principal.py) cuida da câmera, das janelas e do YOLO em segundo
plano; o núcleo cuida da lógica: rastrear, contar, reconhecer, cadastrar e
montar as duas telas.
"""
import time

from contagem import ContadorDeEntradas
from embeddings import LARGURA_MINIMA
from estatisticas import (HistoricoPorMinuto, MediaMovel, MedidorDeCpu,
                          ler_ram, ler_temperatura, formatar_hora)
from mao import mao_da_pessoa, pessoa_da_frente
from fluxo import CALIBRAR, ESPERA, FIM, NOME, POSES_, FluxoDeCadastro
from gestos import GESTO_MAO_ABERTA, GatilhoPorTempo
from poses import razoes_da_cabeca
from identidades import (GerenteDeIdentidades, decidir, rosto_de_frente,
                         associar_rostos, largura_do_rosto)
from rastreador import Rastreador

PASSO_DA_LINHA = 0.02
COR_CONHECIDO = (52, 211, 153)       # verde
COR_DESCONHECIDO = (34, 211, 238)    # ciano
COR_CADASTRANDO = (251, 191, 36)     # amarelo
INTERVALO_TOUCH_S = 0.10             # a tela touch muda pouco: ~10 quadros/s
INTERVALO_ROSTO_S = 0.15             # rosto no dia a dia: ~6 vezes por segundo
INTERVALO_ROSTO_MUITOS_S = 0.40      # com 3+ candidatos a reconhecer
ALTURA_MIN_RECONHECER = 0.35         # só procura rosto de quem está perto
ESPERA_SEM_ROSTO_S = 1.2             # não achou rosto útil: tenta mais tarde
ALTURA_MIN_GESTO = 0.40              # gesto só de quem está perto
MARGEM_PARA_ROUBAR_NOME = 0.05       # nota extra p/ tirar um nome de outra pessoa
INTERVALO_GESTO_LENTO_S = 0.25       # procurando a mão: ~4 vezes por segundo
INTERVALO_GESTO_RAPIDO_S = 0.08      # mão à vista: ~12 vezes por segundo
MAO_ATIVA_S = 1.5                    # tempo em modo rápido depois de ver a mão
MAO_VISIVEL_S = 0.35                 # esqueleto fica na tela este tempo
GUIA_LINHA_S = 4.0                   # linha visível no touch após mexer nela
LINHA_NA_TV = False                  # True = mostra a linha amarela na TV


def _caixa_da_malha(pontos):
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    return (min(xs), min(ys), max(xs), max(ys))


class Nucleo:
    def __init__(self, banco, extrair, rosto, gestos, painel, console,
                 config, registro=None, lotacao_max=None, agora=None):
        """extrair(frame, pontos)->embedding|None; rosto.detectar_todos(frame);
        gestos.detectar(frame)->(nome, conf) ou None para desligar."""
        self.banco, self.extrair = banco, extrair
        self.rosto, self.gestos = rosto, gestos
        self.painel, self.console = painel, console
        self.config, self.registro = config, registro
        self.lotacao_max = lotacao_max

        self.rastreador = Rastreador()
        self.identidades = GerenteDeIdentidades()
        self.fluxo = FluxoDeCadastro(banco, extrair)
        self.gatilho = GatilhoPorTempo(segurar_s=1.0, recarga_s=3.0)
        self.historico = HistoricoPorMinuto(30)
        self.cpu = MedidorDeCpu()
        self._fps = MediaMovel(alpha=0.1)
        self.latencia_ms = 0.0
        self.sair = False

        self.linha_y = float(config.obter("linha_y", 0.5))
        self.inverter = bool(config.obter("inverter", False))
        self.contador = ContadorDeEntradas(*self._linha(), self.inverter)
        self.contador.inferir_nascimento = bool(
            config.obter("inferir_nascimento", True))

        self._pistas = []
        self._pid_cadastro = None
        self._ultimo_rosto_t = -1e9
        self._ultimo_gesto_t = -1e9
        self._mao = None                 # pontos da mão da pessoa da frente
        self._mao_t = -1e9               # quando foi vista pela última vez
        self._progresso_palma = 0.0
        self._guia_ate = -1e9
        self._ultimo_agora = None
        self._inicio = None
        self._sistema = {}
        self._sistema_ate = -1e9
        self._img_touch = None
        self._touch_ate = -1e9
        # tempo gasto (ms, média móvel) em cada parte, para o log
        self.tempos = {k: MediaMovel(alpha=0.1)
                       for k in ("rosto", "gesto", "tv", "touch")}

    # ---------- linha de contagem ----------
    def _linha(self):
        return (0.0, self.linha_y), (1.0, self.linha_y)

    def _aplicar_linha(self):
        a, b = self._linha()
        self.contador.mover_linha(a, b, self.inverter)
        self.config.definir(linha_y=round(self.linha_y, 3),
                            inverter=self.inverter)

    # ---------- ações do monitor touch ----------
    def _tratar_toque(self, toque, agora):
        x, y = toque
        if self.fluxo.estado == NOME:
            self.fluxo.tocar_teclado(x, y, agora)
            return
        acao = self.console.tocar(x, y, self.fluxo.estado, agora)
        if acao == "cadastrar":
            self.fluxo.iniciar(agora)
        elif acao == "aceitar":
            self.fluxo.aceitar(agora)
        elif acao == "cancelar":
            self.fluxo.cancelar(agora=agora)
        elif acao == "linha_cima":
            self.linha_y = max(0.1, self.linha_y - PASSO_DA_LINHA)
            self._aplicar_linha()
            self._guia_ate = agora + GUIA_LINHA_S
        elif acao == "linha_baixo":
            self.linha_y = min(0.9, self.linha_y + PASSO_DA_LINHA)
            self._aplicar_linha()
            self._guia_ate = agora + GUIA_LINHA_S
        elif acao == "inverter":
            self.inverter = not self.inverter
            self._aplicar_linha()
            self._guia_ate = agora + GUIA_LINHA_S
        elif acao == "zerar":
            self.contador.reiniciar()
            self.historico.reiniciar()
        elif acao == "sair":
            self.sair = True

    def _tratar_tecla(self, tecla, agora):
        if tecla in (-1, 255, None):
            return
        if tecla == 27 and self.fluxo.ativo:
            self.fluxo.cancelar(agora=agora)
        elif self.fluxo.estado == NOME:
            self.fluxo.tecla_fisica(tecla, agora)
        elif tecla in (ord("q"), ord("Q")) and self.fluxo.estado == ESPERA:
            self.sair = True

    # ---------- um quadro ----------
    def passo(self, frame, agora, deteccoes=None, toque=None, tecla=None):
        if self._inicio is None:
            self._inicio = agora
        if self._ultimo_agora is not None and agora > self._ultimo_agora:
            self._fps.somar(1.0 / (agora - self._ultimo_agora))
        self._ultimo_agora = agora
        h, w = frame.shape[:2]

        # 1) rastreamento (só quando chegou uma detecção nova)
        if deteccoes is not None:
            self._pistas = self.rastreador.atualizar(deteccoes, agora)
        visiveis = [p for p in self._pistas if p.visivel]

        # 2) rostos: no cadastro a cada quadro; no dia a dia só de vez em
        # quando e só se alguém ainda precisa ser reconhecido (economiza CPU)
        rostos = []
        candidatos = []
        rodou_rosto = False
        pesado = False                   # já fez trabalho pesado neste quadro
        t0 = time.perf_counter()
        if self.fluxo.ativo:
            rostos = self.rosto.detectar_todos(frame)
            pesado = True
        else:
            # só quem está perto o bastante para ter um rosto reconhecível
            candidatos = [p for p in visiveis
                          if p.altura >= ALTURA_MIN_RECONHECER
                          and self.identidades.precisa_tentar(p.id, agora)]
            intervalo = (INTERVALO_ROSTO_MUITOS_S if len(candidatos) >= 3
                         else INTERVALO_ROSTO_S)
            if candidatos and agora - self._ultimo_rosto_t >= intervalo:
                self._ultimo_rosto_t = agora
                rostos = self.rosto.detectar_todos(frame)
                rodou_rosto = True
                pesado = True
        if rodou_rosto or rostos:
            self.tempos["rosto"].somar((time.perf_counter() - t0) * 1000)
        caixas = {p.id: p.caixa for p in visiveis}
        rosto_de = associar_rostos(rostos, caixas)
        if rodou_rosto:
            for p in candidatos:                 # sem rosto útil: espera
                pts = rosto_de.get(p.id)
                if pts is None or largura_do_rosto(pts, w) < LARGURA_MINIMA:
                    self.identidades.adiar(p.id, agora, ESPERA_SEM_ROSTO_S)

        # 3) entradas e saídas
        eventos = self.contador.atualizar(
            {p.id: p.pes for p in self._pistas}, agora,
            {p.id: agora - p.criada_em for p in self._pistas})
        for pid, ev in eventos:
            if ev == "entrou":
                self.historico.registrar(time.time())
            if self.registro:
                self.registro.escrever(ev, pid)

        # 4) reconhecimento (no máximo uma pessoa por quadro): só rosto de
        # frente e grande; um nome nunca vale para duas pessoas ao mesmo tempo
        if not self.fluxo.ativo:
            for pid, pontos in rosto_de.items():
                if not self.identidades.precisa_tentar(pid, agora):
                    continue
                if largura_do_rosto(pontos, w) < LARGURA_MINIMA or \
                        not rosto_de_frente(razoes_da_cabeca(pontos)):
                    self.identidades.adiar(pid, agora, ESPERA_SEM_ROSTO_S / 3)
                    continue
                emb = self.extrair(frame, pontos)
                pesado = True
                if emb is None:
                    continue
                nome, nota = decidir(self.banco.ranking(emb),
                                     self.identidades.negados(pid))
                if nome is not None:
                    dono = self.identidades.dono_do_nome(nome, menos_pid=pid)
                    if dono is not None and dono[0] in caixas and \
                            nota < dono[1] + MARGEM_PARA_ROUBAR_NOME:
                        nome = None          # já é de outra pessoa na tela
                self.identidades.registrar(pid, nome, nota, agora)
                break
        self.identidades.resolver_unicidade({p.id for p in visiveis})
        self.identidades.esquecer_ausentes({p.id for p in self._pistas})

        # 5) cadastro: gesto, toque, teclado e o passo da máquina de estados
        if toque is not None:
            self._tratar_toque(toque, agora)
        self._tratar_tecla(tecla, agora)

        frente = pessoa_da_frente(visiveis)
        # (gesto só de quem está perto, e nunca no mesmo quadro de outro
        # trabalho pesado: espalha o custo e evita travadinhas)
        if self.fluxo.estado == ESPERA and self.gestos is not None and \
                frente is not None and frente.altura >= ALTURA_MIN_GESTO and \
                not pesado:
            intervalo = (INTERVALO_GESTO_RAPIDO_S
                         if agora - self._mao_t < MAO_ATIVA_S
                         else INTERVALO_GESTO_LENTO_S)
            if agora - self._ultimo_gesto_t >= intervalo:
                self._ultimo_gesto_t = agora
                tg = time.perf_counter()
                res = self.gestos.detectar(frame)
                self.tempos["gesto"].somar((time.perf_counter() - tg) * 1000)
                gesto = res[0] if res else None
                pontos = getattr(self.gestos, "pontos", None)
                # só vale a mão de quem está na frente (a de maior caixa)
                de_quem_esta_na_frente = (pontos is not None and
                                          mao_da_pessoa(pontos, frente.caixa))
                if de_quem_esta_na_frente:
                    self._mao, self._mao_t = pontos, agora
                ativo = de_quem_esta_na_frente and gesto == GESTO_MAO_ABERTA
                self._progresso_palma, disparou = self.gatilho.update(
                    ativo, agora)
                if disparou:
                    self.fluxo.iniciar(agora)
        elif self.fluxo.ativo or frente is None or \
                frente.altura < ALTURA_MIN_GESTO:
            self._mao = None
            self._progresso_palma = 0.0

        rosto_cadastro, pid_cadastro = None, None
        if self.fluxo.ativo and rostos:
            rosto_cadastro = max(rostos, key=lambda m: largura_do_rosto(m, w))
            for pid, pontos in rosto_de.items():
                if pontos is rosto_cadastro:
                    pid_cadastro = pid
        if self.fluxo.estado in (CALIBRAR, POSES_):
            self._pid_cadastro = pid_cadastro
        self.fluxo.passo(frame, rosto_cadastro, agora)
        novo = self.fluxo.pop_cadastrado()
        if novo and self._pid_cadastro is not None:
            self.identidades.definir(self._pid_cadastro, novo, agora=agora)

        # 6) o que mostrar
        pessoas = self._pessoas_para_mostrar(visiveis, rosto_de,
                                             rosto_cadastro, agora)
        dados = self._dados(agora, len(visiveis))
        if self.fluxo.ativo:
            modo = "cadastro"
            sub = self.fluxo.aviso(agora) or self.fluxo.subtitulo
            cadastro = (self.fluxo.titulo, sub)
            barra = (self.fluxo.progresso
                     if self.fluxo.estado in (CALIBRAR, POSES_) else None)
        else:
            modo = "convite" if visiveis else "ocioso"
            cadastro, barra = None, None

        a, b = self._linha()
        mao_tv = None
        if self._mao is not None and agora - self._mao_t < MAO_VISIVEL_S \
                and not self.fluxo.ativo:
            mao_tv = (self._mao, self._progresso_palma)
        tt = time.perf_counter()
        tv = self.painel.compor(frame, dados, pessoas, modo=modo,
                                t=agora - self._inicio,
                                linha=(a, b) if LINHA_NA_TV else None,
                                cadastro=cadastro, barra=barra, mao=mao_tv)
        self.tempos["tv"].somar((time.perf_counter() - tt) * 1000)

        tocou = toque is not None or tecla not in (None, -1, 255)
        if tocou or self._img_touch is None or agora >= self._touch_ate:
            vm = {
                "estado": self.fluxo.estado, "titulo": self.fluxo.titulo,
                "subtitulo": self.fluxo.subtitulo,
                "progresso": self.fluxo.progresso,
                "aviso": self.fluxo.aviso(agora), "camera": frame,
                "pessoas": pessoas, "linha": (a, b),
                "inverter": self.inverter, "dentro": self.contador.dentro,
                "entraram": self.contador.entraram,
                "sairam": self.contador.sairam,
                "cadastradas": len(self.banco.listar()),
                "poses_feitas": self.fluxo.poses_feitas,
                "pose_atual": self.fluxo.pose_atual,
            }
            tt = time.perf_counter()
            self._img_touch = self.console.desenhar(
                vm, agora, teclado=self.fluxo.teclado,
                mostrar_linha=agora < self._guia_ate)
            self.tempos["touch"].somar((time.perf_counter() - tt) * 1000)
            self._touch_ate = agora + INTERVALO_TOUCH_S
        return tv, self._img_touch

    def resumo_de_desempenho(self, pessoas):
        t = {k: int(v.valor) for k, v in self.tempos.items()}
        return (f"[desempenho] {self._fps.valor:.1f} FPS | pessoas {pessoas} | "
                f"rosto {t['rosto']} ms | gesto {t['gesto']} ms | "
                f"tv {t['tv']} ms | touch {t['touch']} ms | "
                f"yolo {self.latencia_ms:.0f} ms | "
                f"entradas {self.contador.entraram} "
                f"(inferidas {self.contador.inferidos}) "
                f"saídas {self.contador.sairam}")

    # ---------- partes ----------
    def _pessoas_para_mostrar(self, visiveis, rosto_de, rosto_cadastro,
                              agora):
        pessoas = []
        for p in visiveis:
            pontos = rosto_de.get(p.id)
            cadastrando = (self.fluxo.ativo and pontos is not None
                           and pontos is rosto_cadastro)
            if cadastrando:
                rotulo, cor = "Cadastrando…", COR_CADASTRANDO
            else:
                rotulo = self.identidades.rotulo_com_confianca(p.id)
                cor = (COR_CONHECIDO if self.identidades.conhecido(p.id)
                       else COR_DESCONHECIDO)
            # entre uma detecção e outra (o YOLO roda ~12x por segundo), a
            # caixa continua andando com a velocidade da pessoa
            dt = min(max(agora - p.ultima_vez, 0.0), 0.12)
            dx, dy = p.vel[0] * dt, p.vel[1] * dt
            x0, y0, x1, y1 = p.caixa
            caixa = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
            pessoas.append({"caixa": caixa, "rotulo": rotulo, "cor": cor,
                            "pontos": pontos if cadastrando else ()})
        if rosto_cadastro is not None and not any(
                pt is rosto_cadastro for pt in rosto_de.values()):
            pessoas.append({"caixa": _caixa_da_malha(rosto_cadastro),
                            "rotulo": "Cadastrando…",
                            "cor": COR_CADASTRANDO,
                            "pontos": rosto_cadastro})
        return pessoas

    def _dados(self, agora, na_camera):
        # números do sistema mudam a cada quadro; congelados por 1 s para o
        # painel não precisar ser redesenhado o tempo todo
        if agora >= self._sistema_ate:
            self._sistema = {
                "fps": round(self._fps.valor, 1),
                "temp": round(ler_temperatura(), 0),
                "cpu": round(self.cpu.percentual(), 0),
                "ram": round(ler_ram(), 0),
                "latencia_ms": round(self.latencia_ms, 0),
                "uptime_s": int(agora - self._inicio),
                "hora": formatar_hora(),
                "historico": self.historico.serie(),
            }
            self._sistema_ate = agora + 1.0
        dados = dict(self._sistema)
        dados.update(entraram=self.contador.entraram,
                     sairam=self.contador.sairam,
                     dentro=self.contador.dentro, na_camera=na_camera,
                     lotacao_max=self.lotacao_max)
        return dados
