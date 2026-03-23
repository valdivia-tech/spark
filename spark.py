#!/usr/bin/env python3
"""
Spark CLI — agente de código eléctrico para DIgSILENT PowerFactory.

Uso:
    uv run spark "corre un flujo de potencia en BD_2030.pfd"
    uv run spark -i
"""

import sys
from pathlib import Path

from config import load_dotenv


def main():
    load_dotenv()

    from config import WORKSPACE
    Path(WORKSPACE).mkdir(parents=True, exist_ok=True)

    # Modo interactivo
    if len(sys.argv) > 1 and sys.argv[1] in ("-i", "--interactive"):
        interactive_mode()
        return

    # Prompt desde argumentos
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        from agent import run
        run(prompt)
        return

    # Prompt desde stdin
    if not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
        if prompt:
            from agent import run
            run(prompt)
            return

    # Sin argumentos: modo interactivo
    interactive_mode()


def interactive_mode():
    from agent import run

    print("Spark — agente de codigo electrico")
    print("Escribi una instruccion o 'q' para salir.\n")

    while True:
        try:
            prompt = input("spark> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not prompt:
            continue
        if prompt.lower() in ("q", "quit", "exit", "salir"):
            break

        run(prompt)
        print()


if __name__ == "__main__":
    main()
