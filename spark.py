#!/usr/bin/env python3
"""
Spark CLI — agente de código eléctrico para DIgSILENT PowerFactory.

Uso:
    python spark.py "corre un flujo de potencia en BD_2030.pfd"
    python spark.py --interactive
    echo "lista las barras de 110kV" | python spark.py
"""

import sys
import os
from pathlib import Path

from config import WORKSPACE


def main():
    # Crear workspace si no existe
    Path(WORKSPACE).mkdir(parents=True, exist_ok=True)

    # Modo interactivo
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
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
    """Loop interactivo — escribís instrucciones, Spark las ejecuta."""
    from agent import run

    print("⚡ Spark — agente de código eléctrico")
    print("   Escribí una instrucción o 'salir' para terminar.\n")

    while True:
        try:
            prompt = input("spark> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nChao.")
            break

        if not prompt:
            continue
        if prompt.lower() in ("salir", "exit", "quit", "q"):
            print("Chao.")
            break

        run(prompt)
        print()


if __name__ == "__main__":
    main()
