"""Ajuste de cor da webcam USB, ao vivo.

Rodar:  DISPLAY=:0 python ajustar_cor.py

Teclas (com a janela selecionada):
    D  -> aumenta o valor do balanço de branco (+250)
    A  -> diminui o valor (-250)
    G  -> GUARDA o valor escolhido (vai para ajuste_cor.txt) e sai
    Q  -> sai sem guardar

Olhe para qual lado a imagem fica menos azulada; pare quando a pele da mão
parecer natural e uma parede/papel branco parecer branco.
"""
import cv2

from camera import ARQUIVO_COR, Camera, definir_balanco_branco, ler_ajuste_salvo

PASSO = 250
MINIMO, MAXIMO = 2000, 10000


def main():
    cam = Camera(preferir="usb")
    if cam.tipo != "usb":
        print("Este ajuste é só para webcam USB.")
        cam.close()
        return

    kelvin = ler_ajuste_salvo() or 5000
    definir_balanco_branco(cam.indice_usb, kelvin)
    print("D = aumenta | A = diminui | G = guardar | Q = sair sem guardar")

    try:
        while True:
            frame = cam.read()
            if frame is None:
                continue

            cv2.putText(frame, f"Balanco de branco: {kelvin}", (20, 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 3)
            cv2.putText(frame, "D = aumenta   A = diminui", (20, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame, "G = guardar   Q = sair", (20, 125),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.imshow("Ajuste de cor", frame)

            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (ord("d"), ord("D")):
                kelvin = min(kelvin + PASSO, MAXIMO)
                definir_balanco_branco(cam.indice_usb, kelvin)
                print(f"valor: {kelvin}")
            elif tecla in (ord("a"), ord("A")):
                kelvin = max(kelvin - PASSO, MINIMO)
                definir_balanco_branco(cam.indice_usb, kelvin)
                print(f"valor: {kelvin}")
            elif tecla in (ord("g"), ord("G")):
                with open(ARQUIVO_COR, "w", encoding="utf-8") as arq:
                    arq.write(str(kelvin))
                print(f"Guardado: {kelvin} (arquivo {ARQUIVO_COR})")
                break
            elif tecla in (ord("q"), ord("Q")):
                print("Saiu sem guardar.")
                break
    finally:
        cam.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()