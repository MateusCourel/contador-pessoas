import unittest

from organizar_telas import (escolher, ini_corrigido, interpretar_wlr_randr,
                             planejar)

TOUCH = '''HDMI-A-%d "DO NOT USE - RTK CX101 (HDMI-A-%d)"
  Enabled: yes
  Modes:
    800x600 px, 60.317001 Hz
    1280x720 px, 60.000000 Hz
    1920x1080 px, 60.000000 Hz%s
    1280x800 px, 59.995998 Hz%s
  Position: %s
'''
TV = '''HDMI-A-%d "LG Electronics LG TV SSCR (HDMI-A-%d)"
  Enabled: yes
  Modes:
    1280x720 px, 60.000000 Hz
    1920x1080 px, 24.000000 Hz
    1920x1080 px, 60.000000 Hz%s
    3840x2160 px, 60.000000 Hz%s
  Position: %s
'''


def tela_touch(n, atual, pos):
    if atual == "touch":
        return TOUCH % (n, n, "", " (preferred, current)", pos)
    return TOUCH % (n, n, " (current)", " (preferred)", pos)


def tela_tv(n, atual, pos):
    if atual == "tv":
        return TV % (n, n, " (current)", " (preferred)", pos)
    return TV % (n, n, "", " (preferred, current)", pos)


class TesteOrganizar(unittest.TestCase):
    def test_ja_certo_nao_faz_nada(self):
        s = interpretar_wlr_randr(tela_touch(1, "touch", "0,0") +
                                  tela_tv(2, "tv", "1280,0"))
        self.assertEqual(planejar(s), [])

    def test_portas_trocadas_e_tv_em_4k(self):
        s = interpretar_wlr_randr(tela_tv(1, "4k", "0,0") +
                                  tela_touch(2, "1080", "1280,0"))
        touch, tv = escolher(s)
        self.assertEqual(touch["nome"], "HDMI-A-2")
        self.assertEqual(tv["nome"], "HDMI-A-1")
        a = planejar(s)
        i = a.index("HDMI-A-2")
        self.assertEqual(a[i:i + 5], ["HDMI-A-2", "--mode", "1280x800@59.996Hz",
                                      "--pos", "0,0"])
        self.assertIn("1920x1080@60.000Hz", a)
        self.assertIn("1280,0", a)

    def test_so_uma_tela_nao_mexe(self):
        s = interpretar_wlr_randr(tela_touch(1, "touch", "0,0"))
        self.assertEqual(planejar(s), [])

    def test_ini_aponta_para_as_portas_certas(self):
        velho = ("[input]\nxkb_layout=br\n\n[input-device:TSTP MTouch]\n"
                 "output = HDMI-A-1\n\n[output:HDMI-A-1]\nmode = 1280x800@60\n"
                 "position = 0,0\n\n[output:HDMI-A-2]\nmode = 1920x1080@60\n"
                 "position = 1280,0\n")
        novo = ini_corrigido(velho, "HDMI-A-2", "HDMI-A-1")
        self.assertIn("[input]\nxkb_layout=br", novo)
        self.assertIn("[input-device:TSTP MTouch]\noutput = HDMI-A-2", novo)
        self.assertIn("[output:HDMI-A-2]\nmode = 1280x800@60\nposition = 0,0",
                      novo)
        self.assertIn("[output:HDMI-A-1]\nmode = 1920x1080@60\n"
                      "position = 1280,0", novo)
        self.assertEqual(novo.count("[output:"), 2)
        self.assertEqual(novo.count("TSTP MTouch"), 1)

    def test_ini_ja_certo_fica_igual(self):
        velho = ini_corrigido("[input]\nxkb_layout=br\n", "HDMI-A-1",
                              "HDMI-A-2")
        self.assertEqual(ini_corrigido(velho, "HDMI-A-1", "HDMI-A-2").strip(),
                         velho.strip())


if __name__ == "__main__":
    unittest.main(verbosity=1)
