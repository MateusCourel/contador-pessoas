# Histórico do projeto

## v0.6.1 — Desempenho e tela touch refinada
- YOLO limitado a ~12 detecções por segundo (antes rodava sem parar e ocupava todos os núcleos)
- Rosto e gesto só de vez em quando no dia a dia; a malha do rosto só aparece no cadastro
- Painel sem alocar 6 MB por quadro; caixas acompanham o movimento entre detecções
- Tela touch redesenhada (cantos arredondados, texto suave, prévia maior) com a parte fixa em cache
- A linha de contagem e a seta ENTRADA só aparecem no touch por 4 s ao ajustar a linha

## v0.6 — Programa principal (contagem + reconhecimento + duas telas)
- `deteccao.py` (YOLO11n em NCNN, sem PyTorch) e `rastreador.py` (IDs estáveis)
- `nucleo.py` junta tudo; `principal.py` abre a TV e o monitor touch
- `painel.py` (TV) e `console.py` (touch) com texto acentuado (`texto_pil.py`)
- `fluxo.py`: cadastro como máquina de estados, com cancelamento por inatividade
- `identidades.py`: nome só aparece depois de 2 reconhecimentos iguais (limite 0.45)
- `estatisticas.py`: entradas por minuto, CPU/RAM/temperatura, CSV de eventos, config
- `segundo_plano.py`: YOLO em outra linha de execução
- `yolo_ncnn_teste.py` para conferir o YOLO antes de rodar tudo
- `rosto.py` aceita vários rostos (`detectar_todos`)

## v0.5 — Tela touch com teclado virtual
- `teclado.py`: teclado na tela com maiúsculas automáticas, SHIFT e acentos
- `etapa5_cadastro_touch.py`: cadastro completo pelo toque, em tela cheia
- `teste_toque.py` para conferir a precisão do toque
- `banco.existe_nome` evita cadastros duplicados

## v0.4 — Cadastro com embeddings
- `banco.py` (SQLite), `embeddings.py` (SFace), `etapa4_cadastro.py`
- `reconhecer_teste.py` e `cadastros.py` (listar/apagar, LGPD)
- Aviso de privacidade e consentimento antes de cadastrar

## v0.3 — Rosto e poses da cabeça
- `rosto.py`: malha facial de 478 pontos (MediaPipe FaceLandmarker)
- `poses.py`: yaw/pitch por razões da malha, calibração de frente e guia de 5 poses
- `etapa3_rosto.py` e `test_poses.py` (19 testes)

## v0.2 — Webcam USB sem lag e esqueleto da mão
- Webcam pelo libcamera com troca RGB→BGR e FPS fixo (30)
- Esqueleto verde da mão na etapa 2 (`desenhar_mao`)

## v0.1 — Base: câmera e gesto
- Camera CSI (flat) ou USB com a mesma interface (`camera.py`)
- Gatilho por gesto: mão aberta segurada por 1 s (`gestos.py`)
- Etapa 1: câmera ao vivo com FPS
- Etapa 2: detecção do gesto com barra de progresso
- Testes automatizados da lógica do gatilho

## v0.6.2
- TV: removida a linha amarela horizontal sobre a imagem da câmera.
- TV: esqueleto da mão (linhas verdes, pontos vermelhos) + anel de progresso, desenhado só na mão da pessoa da frente (maior caixa) antes do cadastro.
- Busca de gestos só quando há alguém na frente; mais rápida (0,08 s) quando uma mão aparece, lenta (0,25 s) caso contrário.
- Novo mao.py (+ test_mao.py); test_nucleo.py com novos casos.

## v0.6.3 (para sala cheia)
- Rosto só é procurado em quem está perto (caixa ≥ 35% da altura); quem não mostra rosto útil espera 1,2 s antes de nova tentativa; com 3+ candidatos o detector roda no máximo 2,5x/s (antes ~6x/s sem parar).
- Log de desempenho a cada 10 s no terminal (FPS, pessoas, ms de rosto/gesto/TV/touch/YOLO).
- diagnostico_telas.sh para investigar telas, câmeras e temperatura.

## v0.6.4
- organizar_telas.py: ao abrir, identifica o touch (modo 1280x800) e a TV pelo que são, não pela porta HDMI; força touch 1280x800 em 0,0 e TV 1920x1080@60 em 1280,0 (wlr-randr) e corrige o toque no wayfire.ini (cópia em wayfire.ini.bak). Resolve TV em 4K/portas trocadas. Opção --nao-organizar-telas desliga.

## v0.7 (testado em sala de aula)
**Contagem na porta**
- Quem só é detectado depois de já ter passado da linha (pessoa pequena/longe) agora conta: pista nova que nasce a até 22% da linha e se afasta 6% é contada como entrada/saída (só depois de 3 s do programa abrir; desligue com `"inferir_nascimento": false` em dados/config.json). O resumo de desempenho mostra quantas entradas foram inferidas.
- Rastreador: sem criar ID duplicado para a mesma pessoa (IoU ≥ 0,5), resgate de quem sumiu e reapareceu longe (pela distância do centro), guarda a pista por 2 s, NMS menos agressivo (0,6) para grupos juntos na porta.

**Detecção à distância**
- Limiares do rastreador mais sensíveis (pessoa nova a partir de 0,38; ligação a partir de 0,30).
- Redução da imagem com INTER_AREA (mais detalhe de quem está longe).
- Suporte a modelo YOLO retangular (ex.: 448x256), lendo o tamanho do metadata.yaml. `exportar_yolo.py` gera o modelo; `--yolo-tamanho LxA` força o tamanho.

**Reconhecimento**
- A TV mostra a porcentagem: `Mateus Courel · 78%` (50% = limite de aceitação, 99% = muito parecido; é uma escala de semelhança, não probabilidade).
- Um nome nunca aparece em duas pessoas ao mesmo tempo (fica quem tem a maior nota); quem perde o nome fica proibido de usá-lo.
- Critério mais rígido: média das 2 melhores poses ≥ 0,42, melhor pose ≥ 0,50 e vantagem de 0,06 sobre o 2º colocado do banco.
- Só reconhece rosto de frente e grande; reverifica a cada 2,5 s (a % acompanha o rosto) e solta o nome após 3 erros seguidos.
- Banco com cache em memória (uma multiplicação de matrizes por rosto).

**FPS**
- Painel redesenhado por regiões (a barra de desempenho muda 1x/s sem refazer a tela toda; cartões só quando a contagem muda); câmera redimensionada direto no quadro.
- Tela touch só é reenviada à janela quando mudou.
- Rosto, embedding e gesto nunca no mesmo quadro; gesto só de quem está perto.
