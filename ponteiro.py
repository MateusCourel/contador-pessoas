"""Ponteiro virtual: leva o cursor do mouse para a TV ou para o monitor touch.

Por quê: no Wayfire 0.7 uma janela nova abre no monitor onde está o
ponteiro, e não existe regra para escolher o monitor. Então, antes de abrir
cada janela, empurramos o ponteiro para o lado certo (a TV fica à direita do
touch). É como mexer um mouse de verdade, só que por um dispositivo virtual
(uinput), com a biblioteca evdev.

Precisa de:   sudo apt install -y python3-evdev
e de permissão no /dev/uinput (veja README: grupo "input").
"""
import time


class Ponteiro:
    def __init__(self, fabrica=None, pausa_inicial_s=1.2):
        """fabrica: função que devolve (dispositivo, ecodes); só para testes."""
        self.ui = None
        self.erro = ""
        try:
            if fabrica is None:
                from evdev import UInput
                from evdev import ecodes
                # o libinput só trata o dispositivo como "mouse" se ele tiver
                # também botões; sem BTN_LEFT ele é ignorado
                dispositivo = UInput(
                    {ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT],
                     ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y,
                                     ecodes.REL_WHEEL]},
                    name="contador-ponteiro")
                self.ui, self._e = dispositivo, ecodes
            else:
                self.ui, self._e = fabrica()
        except ImportError:
            self.erro = ("falta o evdev: sudo apt install -y python3-evdev")
        except (OSError, PermissionError) as erro:
            self.erro = (f"sem permissão no /dev/uinput ({erro}); veja o "
                         "README (grupo input)")
        if self.ui and pausa_inicial_s:
            time.sleep(pausa_inicial_s)       # o Wayfire demora a notar o novo "mouse"

    @property
    def disponivel(self):
        return self.ui is not None

    def _empurrar(self, sinal_x, passos=70, passo=120, pausa_s=0.003):
        if not self.ui:
            return False
        for _ in range(passos):
            self.ui.write(self._e.EV_REL, self._e.REL_X, sinal_x * passo)
            self.ui.syn()
            time.sleep(pausa_s)
        time.sleep(0.25)
        return True

    def clicar(self):
        """Um clique esquerdo onde o ponteiro está (fixa o monitor ativo)."""
        if not self.ui:
            return False
        self.ui.write(self._e.EV_KEY, self._e.BTN_LEFT, 1)
        self.ui.syn()
        time.sleep(0.06)
        self.ui.write(self._e.EV_KEY, self._e.BTN_LEFT, 0)
        self.ui.syn()
        time.sleep(0.25)
        return True

    def ir_para_direita(self):
        """Encosta o ponteiro na borda direita (a TV)."""
        return self._empurrar(+1)

    def ir_para_esquerda(self):
        """Encosta o ponteiro na borda esquerda (o monitor touch)."""
        return self._empurrar(-1)

    def fechar(self):
        if self.ui:
            self.ui.close()
            self.ui = None
