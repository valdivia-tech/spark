#!/usr/bin/env python3
"""
Spark CLI — coding agent for DIgSILENT PowerFactory.

Usage:
    uv run spark "run a power flow on BD_2030.pfd"
    uv run spark -i
"""

import sys
from pathlib import Path

from config import load_dotenv


def main():
    load_dotenv()

    from config import get
    Path(get("SPARK_WORKSPACE", "./workspace")).mkdir(parents=True, exist_ok=True)

    if len(sys.argv) > 1 and sys.argv[1] in ("-i", "--interactive"):
        _interactive()
        return

    if len(sys.argv) > 1:
        from agent import run
        run(" ".join(sys.argv[1:]))
        return

    if not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
        if prompt:
            from agent import run
            run(prompt)
            return

    _interactive()


def _interactive():
    from agent import run

    print("Spark — coding agent for electrical power systems")
    print("Type an instruction or 'q' to quit.\n")

    while True:
        try:
            prompt = input("spark> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not prompt:
            continue
        if prompt.lower() in ("q", "quit", "exit"):
            break

        run(prompt)
        print()


if __name__ == "__main__":
    main()
