"""
Spark Agent — loop ReAct con Gemini + herramientas de bash/archivos.
"""

import subprocess
import os
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from google import genai
from google.genai import types

from config import GOOGLE_API_KEY, GEMINI_MODEL, MAX_TURNS, WORKSPACE

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")


# --- Pricing per million tokens ---

MODEL_PRICING = {
    "gemini-3.1-flash-lite-preview": {"input": 0.25, "output": 1.50},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-3-flash-preview": {"input": 0.30, "output": 2.50},
}

DEFAULT_PRICING = {"input": 0.30, "output": 2.50}


@dataclass
class RunStats:
    model: str
    turns: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    duration_seconds: float


# --- Tool implementations ---

def execute_bash(command: str) -> str:
    """Ejecuta un comando bash y devuelve stdout/stderr."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=WORKSPACE,
        )
        output = ""
        if result.stdout:
            output += f"stdout:\n{result.stdout}\n"
        if result.stderr:
            output += f"stderr:\n{result.stderr}\n"
        output += f"exit_code: {result.returncode}"
        return output
    except subprocess.TimeoutExpired:
        return "error: comando excedió timeout de 300 segundos"
    except Exception as e:
        return f"error: {e}"


def read_file(path: str) -> str:
    """Lee el contenido de un archivo."""
    try:
        full_path = Path(WORKSPACE) / path if not os.path.isabs(path) else Path(path)
        return full_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"error: {e}"


def write_file(path: str, content: str) -> str:
    """Escribe contenido a un archivo."""
    try:
        full_path = Path(WORKSPACE) / path if not os.path.isabs(path) else Path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"ok: {full_path}"
    except Exception as e:
        return f"error: {e}"


# --- Tool dispatch ---

TOOL_FUNCTIONS = {
    "execute_bash": execute_bash,
    "read_file": read_file,
    "write_file": write_file,
}


def dispatch_tool(name: str, args: dict) -> str:
    """Ejecuta un tool call y devuelve el resultado como string."""
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"error: tool '{name}' no existe"
    return fn(**args)


# --- Tool declarations for Gemini ---

TOOL_DECLARATIONS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="execute_bash",
            description="Ejecuta un comando bash/shell y devuelve stdout, stderr y exit code.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "command": types.Schema(
                        type="STRING",
                        description="El comando a ejecutar",
                    ),
                },
                required=["command"],
            ),
        ),
        types.FunctionDeclaration(
            name="read_file",
            description="Lee el contenido de un archivo. Paths relativos son relativos al workspace.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(
                        type="STRING",
                        description="Path del archivo a leer",
                    ),
                },
                required=["path"],
            ),
        ),
        types.FunctionDeclaration(
            name="write_file",
            description="Escribe contenido a un archivo. Crea directorios intermedios si no existen.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(
                        type="STRING",
                        description="Path del archivo a escribir",
                    ),
                    "content": types.Schema(
                        type="STRING",
                        description="Contenido a escribir",
                    ),
                },
                required=["path", "content"],
            ),
        ),
    ]
)


# --- Agent loop ---

def _extract_usage(response) -> tuple[int, int]:
    """Extrae input/output tokens de una respuesta de Gemini."""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return 0, 0
    return (
        getattr(usage, "prompt_token_count", 0) or 0,
        getattr(usage, "candidates_token_count", 0) or 0,
    )


def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calcula costo en USD."""
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def run(prompt: str, verbose: bool = True) -> str:
    """
    Ejecuta el agente Spark con un prompt.

    Args:
        prompt: Instrucción para el agente
        verbose: Si True, imprime tool calls y respuestas intermedias

    Returns:
        Respuesta final del agente
    """
    client = genai.Client(api_key=GOOGLE_API_KEY)

    chat = client.chats.create(
        model=GEMINI_MODEL,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[TOOL_DECLARATIONS],
        ),
    )

    if verbose:
        print(f"\n{'='*60}")
        print(f"Spark — {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        print(f"{'='*60}\n")

    start_time = time.time()
    total_input_tokens = 0
    total_output_tokens = 0

    response = chat.send_message(prompt)
    inp, out = _extract_usage(response)
    total_input_tokens += inp
    total_output_tokens += out
    turns = 0

    while turns < MAX_TURNS:
        # Extraer function calls de la respuesta
        function_calls = []
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    function_calls.append(part.function_call)

        # Si no hay function calls, terminamos
        if not function_calls:
            break

        # Ejecutar cada tool call
        tool_responses = []
        for fc in function_calls:
            args = dict(fc.args) if fc.args else {}
            result = dispatch_tool(fc.name, args)

            if verbose:
                if fc.name == "execute_bash":
                    print(f"  $ {args.get('command', '')}")
                elif fc.name == "write_file":
                    print(f"  write -> {args.get('path', '')}")
                elif fc.name == "read_file":
                    print(f"  read <- {args.get('path', '')}")

                result_preview = result[:200] + "..." if len(result) > 200 else result
                print(f"    {result_preview}\n")

            tool_responses.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result},
                )
            )

        # Enviar resultados al modelo
        response = chat.send_message(tool_responses)
        inp, out = _extract_usage(response)
        total_input_tokens += inp
        total_output_tokens += out
        turns += 1

    # Extraer texto final
    final_text = ""
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if part.text:
                final_text += part.text

    duration = time.time() - start_time
    total_tokens = total_input_tokens + total_output_tokens
    cost = _calculate_cost(GEMINI_MODEL, total_input_tokens, total_output_tokens)

    stats = RunStats(
        model=GEMINI_MODEL,
        turns=turns,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost,
        duration_seconds=round(duration, 2),
    )

    # Guardar stats en results/
    stats_path = Path(WORKSPACE) / "results" / "_last_run_stats.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(asdict(stats), indent=2))

    if verbose:
        print(f"\n{'='*60}")
        print(f"Spark completó en {turns} turns | {duration:.1f}s")
        print(f"Tokens: {total_input_tokens:,} in + {total_output_tokens:,} out = {total_tokens:,} total")
        print(f"Costo: ${cost:.6f} USD")
        print(f"{'='*60}\n")
        print(final_text)

    return final_text
