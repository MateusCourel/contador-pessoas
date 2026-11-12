#!/bin/bash
# Mostra tudo que preciso para entender as telas. Rode no terminal da Pi:
#   cd ~/contador-pessoas && bash diagnostico_telas.sh
echo "=== wlr-randr (telas do Wayfire) ==="
wlr-randr 2>&1
echo
echo "=== xrandr (telas vistas pelo programa) ==="
DISPLAY=:0 xrandr --query 2>&1 | grep -E "connected|^Screen"
echo
echo "=== wayfire.ini (telas e toque) ==="
grep -n -A6 -E "^\[output|^\[input-device" ~/.config/wayfire.ini 2>&1
echo
echo "=== câmeras USB/CSI ==="
v4l2-ctl --list-devices 2>&1 | head -20
echo
echo "=== temperatura e limite de CPU ==="
vcgencmd measure_temp; vcgencmd get_throttled
echo
echo "=== últimas linhas do log do programa ==="
tail -30 dados/principal.log 2>&1
