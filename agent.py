"""Spark — ReAct agent loop with Gemini + bash/file tools."""

import subprocess
import os
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from google import genai
from google.genai import types

import config

PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT = (PROMPTS_DIR / "system.md").read_text(encoding="utf-8")

# Pricing per million tokens
MODEL_PRICING = {
    "gemini-3.1-flash-lite-preview": {"input": 0.25, "output": 1.50},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-3-flash-preview": {"input": 0.30, "output": 2.50},
}


@dataclass
class RunStats:
    model: str
    turns: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    duration_seconds: float


# --- Tools ---

def _tool(name: str, description: str, params: dict) -> types.FunctionDeclaration:
    """Helper to declare a tool with less boilerplate."""
    return types.FunctionDeclaration(
        name=name,
        description=description,
        parameters=types.Schema(
            type="OBJECT",
            properties={
                k: types.Schema(type="STRING", description=v)
                for k, v in params.items()
            },
            required=list(params.keys()),
        ),
    )


TOOL_DECLARATIONS = types.Tool(function_declarations=[
    _tool("execute_bash", "Run a bash command. Returns stdout, stderr, exit code.", {
        "command": "The command to run",
    }),
    _tool("read_file", "Read a file. Relative paths resolve from workspace.", {
        "path": "File path to read",
    }),
    _tool("write_file", "Write content to a file. Creates parent dirs if needed.", {
        "path": "File path to write",
        "content": "Content to write",
    }),
])


def _execute_bash(command: str, workspace: str) -> str:
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=300, cwd=workspace)
        parts = []
        if r.stdout:
            parts.append(f"stdout:\n{r.stdout}")
        if r.stderr:
            parts.append(f"stderr:\n{r.stderr}")
        parts.append(f"exit_code: {r.returncode}")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return "error: command timed out after 300s"
    except Exception as e:
        return f"error: {e}"


def _read_file(path: str, workspace: str) -> str:
    try:
        full = Path(workspace) / path if not os.path.isabs(path) else Path(path)
        return full.read_text(encoding="utf-8")
    except Exception as e:
        return f"error: {e}"


def _write_file(path: str, content: str, workspace: str) -> str:
    try:
        full = Path(workspace) / path if not os.path.isabs(path) else Path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return f"ok: {full}"
    except Exception as e:
        return f"error: {e}"


def _dispatch(name: str, args: dict, workspace: str) -> str:
    if name == "execute_bash":
        return _execute_bash(args.get("command", ""), workspace)
    if name == "read_file":
        return _read_file(args.get("path", ""), workspace)
    if name == "write_file":
        return _write_file(args.get("path", ""), args.get("content", ""), workspace)
    return f"error: unknown tool '{name}'"


# --- Agent loop ---

def _extract_usage(response) -> tuple[int, int]:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return 0, 0
    return (
        getattr(usage, "prompt_token_count", 0) or 0,
        getattr(usage, "candidates_token_count", 0) or 0,
    )


def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, {"input": 0.30, "output": 2.50})
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def _get_function_calls(response) -> list:
    calls = []
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if part.function_call:
                calls.append(part.function_call)
    return calls


def _get_text(response) -> str:
    if not response.candidates:
        return ""
    return "".join(p.text for p in response.candidates[0].content.parts if p.text)


def run(prompt: str, verbose: bool = True) -> str:
    """Run the Spark agent with a prompt. Returns the final text response."""
    model = config.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
    workspace = config.get("SPARK_WORKSPACE", "./workspace")
    max_turns = int(config.get("MAX_TURNS", "30"))

    client = genai.Client(api_key=config.get("GOOGLE_API_KEY"))
    chat = client.chats.create(
        model=model,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[TOOL_DECLARATIONS],
        ),
    )

    if verbose:
        print(f"\n{'='*60}")
        print(f"Spark — {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        print(f"{'='*60}\n")

    start = time.time()
    total_in, total_out = 0, 0

    response = chat.send_message(prompt)
    inp, out = _extract_usage(response)
    total_in += inp
    total_out += out
    turns = 0

    while turns < max_turns:
        calls = _get_function_calls(response)
        if not calls:
            break

        tool_responses = []
        for fc in calls:
            args = dict(fc.args) if fc.args else {}
            result = _dispatch(fc.name, args, workspace)

            if verbose:
                label = {"execute_bash": f"  $ {args.get('command', '')}",
                         "write_file": f"  write -> {args.get('path', '')}",
                         "read_file": f"  read <- {args.get('path', '')}"}
                print(label.get(fc.name, f"  {fc.name}"))
                preview = result[:200] + "..." if len(result) > 200 else result
                print(f"    {preview}\n")

            tool_responses.append(
                types.Part.from_function_response(name=fc.name, response={"result": result})
            )

        response = chat.send_message(tool_responses)
        inp, out = _extract_usage(response)
        total_in += inp
        total_out += out
        turns += 1

    final_text = _get_text(response)
    duration = time.time() - start
    total_tokens = total_in + total_out
    cost = _calculate_cost(model, total_in, total_out)

    stats = RunStats(
        model=model, turns=turns,
        input_tokens=total_in, output_tokens=total_out,
        total_tokens=total_tokens, cost_usd=cost,
        duration_seconds=round(duration, 2),
    )

    stats_path = Path(workspace) / "results" / "_last_run_stats.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(asdict(stats), indent=2))

    if verbose:
        print(f"\n{'='*60}")
        print(f"Spark completed in {turns} turns | {duration:.1f}s")
        print(f"Tokens: {total_in:,} in + {total_out:,} out = {total_tokens:,}")
        print(f"Cost: ${cost:.6f}")
        print(f"{'='*60}\n")
        print(final_text)

    return final_text
