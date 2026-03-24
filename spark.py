#!/usr/bin/env python3
"""
Spark CLI — coding agent for DIgSILENT PowerFactory.

Usage:
    uv run spark "run a power flow on BD_2030.pfd"
    uv run spark -i
    uv run spark -i --session abc123    # resume session
    uv run spark --sessions             # list sessions
"""

import sys
import json
from pathlib import Path

from config import load_dotenv


def main():
    load_dotenv()

    from config import get
    Path(get("SPARK_WORKSPACE", "./workspace")).mkdir(parents=True, exist_ok=True)

    args = sys.argv[1:]

    # List sessions
    if "--sessions" in args:
        _list_sessions()
        return

    # Parse --session flag
    session_id = None
    if "--session" in args:
        idx = args.index("--session")
        if idx + 1 < len(args):
            session_id = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            print("error: --session requires an ID")
            sys.exit(1)

    # Interactive mode
    if args and args[0] in ("-i", "--interactive"):
        _interactive(session_id)
        return

    # Single command
    if args:
        from agent import Session
        session = Session(session_id)
        session.run(" ".join(args))
        return

    # Stdin
    if not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
        if prompt:
            from agent import Session
            session = Session(session_id)
            session.run(prompt)
            return

    # Default: interactive
    _interactive(session_id)


def _interactive(session_id: str | None = None):
    from agent import Session

    session = Session(session_id)
    label = f"resuming session {session.session_id}" if session_id else f"new session {session.session_id}"

    print(f"Spark — coding agent for electrical power systems")
    print(f"Session: {session.session_id} ({label})")
    print(f"Type an instruction or 'q' to quit.\n")

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

        session.run(prompt)
        print()

    print(f"\nSession {session.session_id} saved.")
    print(f"Resume with: uv run spark -i --session {session.session_id}")
    print(f"Total cost: ${session.total_cost:.6f}")


def _list_sessions():
    from agent import SESSIONS_DIR

    if not SESSIONS_DIR.exists():
        print("No sessions found.")
        return

    sessions = sorted(SESSIONS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not sessions:
        print("No sessions found.")
        return

    print(f"{'ID':<12} {'Model':<32} {'Turns':>6} {'Cost':>10} {'Created'}")
    print("-" * 85)
    for f in sessions:
        try:
            data = json.loads(f.read_text())
            sid = data.get("session_id", f.stem)
            model = data.get("model", "?")
            turns = data.get("total_turns", 0)
            cost = data.get("total_cost_usd", 0)
            created = data.get("created", "?")[:19]
            print(f"{sid:<12} {model:<32} {turns:>6} ${cost:>9.6f} {created}")
        except Exception:
            print(f"{f.stem:<12} (error reading)")


if __name__ == "__main__":
    main()
