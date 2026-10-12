# Contador de Pessoas — projeto base (Raspberry Pi 5)

Etapas prontas nesta versão:

| Arquivo | O que faz |
|---|---|
| `camera.py` | Abre a câmera do flat (CSI) ou a webcam USB com a mesma interface |
| `gestos.py` | Detecta a **mão aberta** e só dispara depois de segurar **1 segundo** |
| `etapa1_camera.py` | Mostra a câmera ao vivo com os FPS |
| `etapa2_gesto.py` | Detecta o gesto, mostra barra de progresso e "dispara o cadastro" |
| `test_gatilho.py` | Testes da lógica de segurar 1 s (não precisa de câmera) |

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

## 4. Problemas comuns

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
- [ ] 3. Detectar rosto e direção da cabeça (pose guiada)
- [ ] 4. Cadastro com embeddings + SQLite
- [ ] 5. Tela touch com teclado virtual
- [ ] 6. Contagem de pessoas (YOLO) e reconhecimento de quem passa
- [ ] 7. Painel web, mapa de calor e alertas
- [ ] 8. Medir a taxa de acerto e melhorar o reconhecimento

Veja o histórico de mudanças em [CHANGELOG.md](CHANGELOG.md).

## 6. Privacidade

O projeto lida com rostos, que são dado biométrico (LGPD). Por isso o
`.gitignore` bloqueia fotos, bancos de dados e embeddings: **nunca** suba esses
arquivos para o repositório. A ideia é guardar apenas os embeddings (números),
não as fotos, e permitir apagar o cadastro de qualquer pessoa.
