# Contador de Pessoas — projeto base (Raspberry Pi 5)

Etapas prontas nesta versão:

| Arquivo | O que faz |
|---|---|
| `camera.py` | Abre a câmera do flat (CSI) ou a webcam USB com a mesma interface |
| `gestos.py` | Detecta a **mão aberta** e só dispara depois de segurar **1 segundo** |
| `etapa1_camera.py` | Mostra a câmera ao vivo com os FPS |
| `etapa2_gesto.py` | Detecta o gesto, mostra barra de progresso e "dispara o cadastro" |
| `rosto.py` | Acha o rosto (478 pontos) e desenha a malha |
| `poses.py` | Lógica das poses da cabeça: frente, esquerda, direita, cima, baixo |
| `etapa3_rosto.py` | Calibra o "olhar de frente" e guia as 5 poses |
| `banco.py` | Guarda pessoas e embeddings no SQLite (`dados/pessoas.db`) |
| `embeddings.py` | Transforma o rosto em 128 números (modelo SFace) |
| `etapa4_cadastro.py` | Cadastro completo: gesto, aviso, 5 poses, nome, gravação |
| `reconhecer_teste.py` | Mostra o nome de quem está na frente da câmera |
| `cadastros.py` | Lista e apaga cadastros |
| `teclado.py` | Teclado virtual para a tela touch (com acentos) |
| `etapa5_cadastro_touch.py` | Cadastro todo pelo toque, em tela cheia |
| `teste_toque.py` | Mostra onde o toque cai, para conferir a precisão |
| `test_teclado.py` | Testes do teclado virtual (não precisa de tela) |
| `test_banco.py` | Testes do banco (não precisa de câmera) |
| `test_gatilho.py` | Testes da lógica de segurar 1 s (não precisa de câmera) |
| `test_poses.py` | Testes da lógica das poses (não precisa de câmera) |

## 1. Instalar (uma vez só)

Copie esta pasta para o Pi em `/home/SEU_USUARIO/contador-pessoas`
(pendrive, GitHub, e-mail para você mesmo... o que for mais fácil).

Abra o terminal no Pi e rode, linha por linha:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-picamera2 python3-opencv wget

# ambiente do projeto (o --system-site-packages é importante: é ele que
# deixa o Python do projeto enxergar o picamera2 e o opencv do sistema)
python3 -m venv --system-site-packages ~/contador
source ~/contador/bin/activate

cd ~/contador-pessoas
pip install mediapipe
```

Baixe o modelo de gestos do Google (fica na mesma pasta dos arquivos .py):

```bash
wget -O gesture_recognizer.task https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task
```

Baixe também o modelo de rosto (etapa 3):

```bash
wget -O face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task
```

E o modelo de reconhecimento (etapa 4):

```bash
wget -O face_recognition_sface_2021dec.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
```

## 2. Rodar

Sempre que abrir um terminal novo, ative o ambiente antes:

```bash
source ~/contador/bin/activate
cd ~/contador-pessoas
```

Teste da lógica (não usa câmera, deve terminar com `OK`):

```bash
python test_gatilho.py
```

**Etapa 1 — ver a câmera:**

```bash
python etapa1_camera.py
```

Deve abrir uma janela com a imagem ao vivo e os FPS. Aperte **Q** para sair.

**Etapa 2 — gesto da mão aberta:**

```bash
python etapa2_gesto.py
```

Mostre a palma aberta para a câmera e segure. Uma barra enche durante 1 segundo;
ao completar aparece "CADASTRO INICIADO!" na tela e no terminal. Tire a mão e
espere ~3 s para poder disparar de novo.

**Etapa 3 — rosto e poses da cabeça:**

```bash
python test_poses.py      # deve terminar com OK
python etapa3_rosto.py
```

Primeiro fique parado olhando de frente até a barra laranja encher
(calibração). Depois siga os pedidos na tela: frente, esquerda, direita, cima
e baixo, segurando cada pose ~1 s. Teclas: **R** recomeça as poses, **C**
calibra de novo, **Q** sai. No terminal aparece `>>> pose confirmada: ...`
(na etapa 4 é aí que a foto será tirada).

Se alguma pose ficar difícil ou fácil demais, ajuste `LIMITE_YAW` e
`LIMITE_PITCH` em `poses.py`. Se "cima" e "baixo" aparecerem trocados, mude
`INVERTER_CIMA_BAIXO` para `True`.

**Etapa 4 — cadastrar uma pessoa:**

```bash
python test_banco.py          # deve terminar com OK
python etapa4_cadastro.py     # cadastra
python reconhecer_teste.py    # confere se reconhece
python cadastros.py           # lista; "apagar 3" apaga a pessoa de id 3
```

No cadastro: mão aberta 1 s, aceitar o aviso (**S**), olhar de frente, as 5
poses, digitar o nome e **ENTER**. **ESC** cancela. Só os embeddings ficam
em `dados/pessoas.db`; as fotos não são guardadas.

**Etapa 5 — cadastro pela tela touch:**

```bash
python test_teclado.py          # deve terminar com OK
python teste_toque.py           # confere se o toque acerta (Q sai)
python etapa5_cadastro_touch.py            # tela cheia, para o monitor touch
python etapa5_cadastro_touch.py --janela   # em janela, para testar
```

Tudo pode ser feito com o dedo: **CADASTRAR** (ou mão aberta), **ACEITO**,
as 5 poses e o nome no teclado da tela. A primeira letra de cada palavra sai
maiúscula sozinha. Para acentuar, toque no acento (´ ` ^ ~) e depois na vogal
(`~` + `a` = ã). Nomes repetidos são recusados. O teclado do computador também
funciona. Para os acentos aparecerem na tela é preciso ter o Pillow e a fonte
DejaVu (`sudo apt install python3-pil fonts-dejavu-core`); sem eles o
teclado funciona do mesmo jeito, só que sem acentos desenhados.

**Etapa 6 — programa principal (contagem + reconhecimento + cadastro):**

```bash
pip install ncnn pillow           # uma vez só, com o ambiente ativo
python yolo_ncnn_teste.py         # confere o YOLO em NCNN (cria yolo_ncnn_teste.jpg)
python principal.py --janela      # teste em janelas
DISPLAY=:0 python principal.py    # TV + monitor touch em tela cheia
python principal.py --video teste.mp4   # usa um vídeo no lugar da câmera
```

Pré-requisito: a pasta `yolo11n_ncnn_model/` (criada pelo `yolo_teste.py`) e os
três modelos das etapas anteriores na mesma pasta. A **TV** mostra o painel
público; o **monitor touch** tem os botões (CADASTRAR, LINHA ▲▼, INVERTER
SENTIDO, ZERAR, SAIR; zerar e sair pedem um segundo toque). A linha de contagem
é horizontal: quem cruza para baixo na imagem conta como entrada (use INVERTER
SENTIDO se a sua porta for o contrário). A posição da linha fica salva em
`dados/config.json` e cada entrada/saída vai para `dados/eventos.csv` (só
hora, evento e número temporário, sem dados pessoais). Nomes só aparecem na TV
para quem se cadastrou; os demais são "Pessoa · ID n".

### Usando o Thonny

Em **Ferramentas → Opções → Interpretador → Alternative Python 3 executable**,
aponte para `/home/SEU_USUARIO/contador/bin/python`. Depois abra
`etapa1_camera.py` ou `etapa2_gesto.py` e clique em Run.

## 3. Ajustes rápidos

- **Só tenho a webcam USB:** em `etapa1_camera.py` / `etapa2_gesto.py`, troque
  `preferir="csi"` por `preferir="usb"`. (Se o CSI falhar, ele já cai
  automaticamente para a USB.)
- **FPS baixo:** diminua para `largura=640, altura=480`. Não use a resolução
  total dos 16MP — o Pi não precisa disso para detectar e fica bem mais lento.
- **Foco:** com a câmera fixa no lugar definitivo, descomente a linha
  `cam.travar_foco(...)` na etapa 1 e teste valores de posição até a imagem
  ficar nítida. (Só faz efeito em câmeras com autofoco.)
- **Gesto mais ou menos "sensível":** em `etapa2_gesto.py`, mude `segurar_s`
  (tempo segurando) ou, em `DetectorDeGestos`, a `confianca_minima`.

- **Webcam USB (Logitech C270):** o `camera.py` abre pelo libcamera e já troca
  vermelho/azul sozinho, a 30 FPS. O FPS fixo é feito com
  `v4l2-ctl --set-ctrl=exposure_dynamic_framerate=0`.

## 4. Problemas comuns

**Janela não abre / "Nenhuma câmera encontrada" logo depois de ter funcionado**
Um programa antigo ainda está segurando a câmera. **Não use Ctrl+Z** para
sair (isso só suspende e a câmera continua presa). Use **Q** na janela ou
Ctrl+C. Para liberar à força: `pkill -9 -f etapa`.

**"Nenhuma câmera encontrada"**
Rode `rpicam-hello --list-cameras`. Se a câmera CSI não aparecer, veja o cabo
(Pi desligado ao encaixar!) e se o sensor precisa de `dtoverlay` no
`/boot/firmware/config.txt` (ex.: `dtoverlay=imx519`).

**Erro de `Qt platform plugin "xcb"` ao abrir a janela**
O MediaPipe instala um OpenCV próprio que briga com o do sistema. Remova o dele
e o Python volta a usar o OpenCV do sistema:

```bash
pip uninstall -y opencv-contrib-python opencv-python
```

**`ModuleNotFoundError: picamera2`**
O ambiente foi criado sem `--system-site-packages`. Apague (`rm -rf ~/contador`)
e refaça o passo de criar o ambiente.

**`ModuleNotFoundError: mediapipe`**
O ambiente não está ativo. Rode `source ~/contador/bin/activate` (o terminal
mostra `(contador)` no começo da linha quando está ativo).

## 5. Roadmap

- [x] 1. Câmera ao vivo (CSI ou USB)
- [x] 2. Gesto da mão aberta como gatilho
- [x] 3. Detectar rosto e direção da cabeça (pose guiada)
- [x] 4. Cadastro com embeddings + SQLite
- [x] 5. Tela touch com teclado virtual
- [x] 6. Contagem de pessoas (YOLO) e reconhecimento de quem passa (programa principal, TV + touch)
- [ ] 7. Painel web, mapa de calor e alertas
- [ ] 8. Medir a taxa de acerto e melhorar o reconhecimento

Veja o histórico de mudanças em [CHANGELOG.md](CHANGELOG.md).

## 6. Privacidade

O projeto lida com rostos, que são dado biométrico (LGPD). Por isso o
`.gitignore` bloqueia fotos, bancos de dados e embeddings: **nunca** suba esses
arquivos para o repositório. A ideia é guardar apenas os embeddings (números),
não as fotos, e permitir apagar o cadastro de qualquer pessoa.
