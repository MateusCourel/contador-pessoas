"""Ver e apagar cadastros (direito de apagar os dados, LGPD).

    python cadastros.py              lista as pessoas
    python cadastros.py apagar 3     apaga a pessoa de id 3
    python cadastros.py apagar todos apaga TODO MUNDO (pede confirmação)
"""
import sys

from banco import Banco


def main():
    banco = Banco()
    args = sys.argv[1:]
    if not args:
        linhas = banco.listar()
        if not linhas:
            print("Nenhuma pessoa cadastrada.")
        for pid, nome, criado, n in linhas:
            print(f"{pid:>3}  {nome:<30} {criado}  ({n} embeddings)")
    elif args[0] == "apagar" and len(args) == 2:
        if args[1] == "todos":
            if input("Apagar TODOS os cadastros? Digite SIM: ") == "SIM":
                for pid, *_ in banco.listar():
                    banco.apagar(pid)
                print("Tudo apagado.")
            else:
                print("Cancelado.")
        elif args[1].isdigit():
            print("Apagado." if banco.apagar(int(args[1]))
                  else "Não existe pessoa com esse id.")
        else:
            print(__doc__)
    else:
        print(__doc__)
    banco.fechar()


if __name__ == "__main__":
    main()
