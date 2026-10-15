# Histórico do projeto

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
