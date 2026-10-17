"""Roda o detector de pessoas (YOLO) numa linha de execução separada.

O NCNN solta o "GIL" do Python enquanto calcula, então o programa principal
continua mostrando a câmera e desenhando as telas na velocidade da câmera,
e o YOLO entrega o resultado dele quando termina.

    ts = DetectorEmSegundoPlano(detector)
    ts.enviar(frame, agora)     # ignorado se o YOLO ainda está ocupado
    r = ts.pegar()              # (deteccoes, agora_do_frame, ms) ou None
"""
import threading
import time
import traceback


class DetectorEmSegundoPlano:
    def __init__(self, detector, intervalo_min_s=0.0):
        """intervalo_min_s: tempo mínimo entre duas detecções. Rodar o YOLO
        'o mais rápido possível' ocupa todos os núcleos do Pi e trava o
        resto do programa; ~12 por segundo bastam para contar."""
        self._detector = detector
        self.intervalo_min_s = intervalo_min_s
        self._ultimo_envio = -1e9
        self._trava = threading.Lock()
        self._evento = threading.Event()
        self._frame = None
        self._agora = 0.0
        self._ocupado = False
        self._resultado = None
        self._parar = False
        self.erros = 0
        self._thread = threading.Thread(target=self._laco, daemon=True)
        self._thread.start()

    def enviar(self, frame, agora):
        """Entrega um quadro (copiado). Devolve False se estava ocupado."""
        with self._trava:
            agora_rel = time.monotonic()
            if self._ocupado or \
                    agora_rel - self._ultimo_envio < self.intervalo_min_s:
                return False
            self._ultimo_envio = agora_rel
            self._frame = frame.copy()
            self._agora = agora
            self._ocupado = True
        self._evento.set()
        return True

    def pegar(self):
        with self._trava:
            r, self._resultado = self._resultado, None
        return r

    def parar(self):
        self._parar = True
        self._evento.set()
        self._thread.join(timeout=2.0)

    def _laco(self):
        while not self._parar:
            self._evento.wait(0.5)
            self._evento.clear()
            if self._parar:
                break
            with self._trava:
                frame, agora, ocupado = self._frame, self._agora, self._ocupado
            if not ocupado:
                continue
            t0 = time.perf_counter()
            try:
                deteccoes = self._detector.detectar(frame)
            except Exception:                    # não derruba o programa
                self.erros += 1
                if self.erros <= 3:
                    traceback.print_exc()
                deteccoes = None
            ms = (time.perf_counter() - t0) * 1000.0
            with self._trava:
                if deteccoes is not None:
                    self._resultado = (deteccoes, agora, ms)
                self._ocupado = False
