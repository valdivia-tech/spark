"""Spark — ReAct agent loop with Gemini + bash/file tools."""

import subprocess
import os
import json
import time
import uuid
import base64
import logging
import threading
from pathlib import Path
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from google import genai
from google.genai import types

import config

log = logging.getLogger("spark")

PROMPTS_DIR = Path(__file__).parent / "prompts"
LEARNED_DIR = PROMPTS_DIR / "learned"

def _build_system_prompt() -> str:
    """Build system prompt with learned experiences index and current date injected."""
    base = (PROMPTS_DIR / "system.md").read_text(encoding="utf-8")
    # Inject the actual date so the model doesn't have to guess
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = base.replace("{YYYY-MM-DD}", today)
    index_file = LEARNED_DIR / "index.md"
    if index_file.exists():
        index = index_file.read_text(encoding="utf-8")
        base += f"\n\n## Available experiences\n\n{index}\n\nRead the relevant files with read_file before writing your script."
    return base

MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]  # seconds
MAX_OUTPUT_CHARS = 10_000  # truncate tool output to prevent context overflow
MAX_CONSECUTIVE_ERRORS = 3  # stop if same error repeats this many times
SCRIPT_TIMEOUT = int(config.get("SCRIPT_TIMEOUT", "600"))  # seconds

_FAILURE_SAVE_PROMPT = (
    "SYSTEM: This task has FAILED. You were stopped because you hit the error/turn/cost limit. "
    "BEFORE responding to the user, you MUST save a failure experience to ../prompts/learned/ "
    "following the [FALLIDO] format from your instructions. "
    "This is mandatory — do NOT skip it. Save what you tried, why it failed, and what to avoid next time. "
    "Then respond to the user explaining the failure."
)

# Pricing per million tokens (https://ai.google.dev/gemini-api/docs/pricing)
MODEL_PRICING = {
    # Gemini 3.x
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
    "gemini-3.1-flash-lite-preview": {"input": 0.25, "output": 1.50},
    # Gemini 2.5
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
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
    script_executions: list = field(default_factory=list)


# --- Tools ---

def _tool(name: str, description: str, params: dict) -> types.FunctionDeclaration:
    return types.FunctionDeclaration(
        name=name,
        description=description,
        parameters=types.Schema(
            type="OBJECT",
            properties={k: types.Schema(type="STRING", description=v) for k, v in params.items()},
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


def _truncate(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + f"\n\n... [TRUNCATED {len(text) - max_chars} chars] ...\n\n" + text[-half:]


def _kill_process_tree(pid: int) -> None:
    """Kill a process and ALL its descendants.

    On Windows with shell=True, subprocess.run spawns cmd.exe → python.exe.
    Killing only the parent (cmd.exe) leaves python.exe orphaned and running
    forever, which silently bypasses SCRIPT_TIMEOUT. This walks the tree.
    """
    try:
        import psutil
    except ImportError:
        # Fallback: best-effort OS tools
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True, timeout=10,
                )
            else:
                os.killpg(os.getpgid(pid), 9)
        except Exception:
            pass
        return
    try:
        parent = psutil.Process(pid)
        descendants = parent.children(recursive=True)
        for child in descendants:
            try:
                child.kill()
            except Exception:
                pass
        parent.kill()
        psutil.wait_procs([parent, *descendants], timeout=5)
    except psutil.NoSuchProcess:
        pass
    except Exception:
        pass


def _execute_bash(
    command: str,
    workspace: str,
    extra_env: dict | None = None,
    pid_callback=None,
    cancel_event: threading.Event | None = None,
) -> str:
    try:
        # Strip comment lines — # is not valid in Windows cmd.exe
        lines = command.split("\n")
        lines = [l for l in lines if not l.strip().startswith("#")]
        command = "\n".join(lines).strip()
        if not command:
            return "error: empty command after stripping comments"
        env = {**os.environ, **(extra_env or {})}

        # Use Popen so we can capture the PID, kill the whole process tree on
        # timeout, and respond to external cancel signals. subprocess.run with
        # shell=True on Windows orphans the python.exe child when the timeout
        # fires (it kills cmd.exe but not its descendants).
        proc = subprocess.Popen(
            command, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=workspace, env=env,
        )
        if pid_callback:
            try:
                pid_callback(proc.pid)
            except Exception:
                pass
        try:
            stdout, stderr = proc.communicate(timeout=SCRIPT_TIMEOUT)
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc.pid)
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except Exception:
                stdout, stderr = "", ""
            if pid_callback:
                try:
                    pid_callback(None)
                except Exception:
                    pass
            return f"error: command timed out after {SCRIPT_TIMEOUT}s"
        finally:
            if pid_callback:
                try:
                    pid_callback(None)
                except Exception:
                    pass

        if cancel_event is not None and cancel_event.is_set():
            # External cancel arrived while we were running — ensure tree is dead.
            _kill_process_tree(proc.pid)
            return "error: cancelled by user"

        parts = []
        if stdout:
            parts.append(f"stdout:\n{_truncate(stdout)}")
        if stderr:
            parts.append(f"stderr:\n{_truncate(stderr)}")
        parts.append(f"exit_code: {returncode}")
        return "\n".join(parts)
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


def _dispatch(
    name: str,
    args: dict,
    workspace: str,
    extra_env: dict | None = None,
    pid_callback=None,
    cancel_event: threading.Event | None = None,
) -> str:
    if name == "execute_bash":
        return _execute_bash(
            args.get("command", ""), workspace, extra_env,
            pid_callback=pid_callback, cancel_event=cancel_event,
        )
    if name == "read_file":
        return _read_file(args.get("path", ""), workspace)
    if name == "write_file":
        return _write_file(args.get("path", ""), args.get("content", ""), workspace)
    return f"error: unknown tool '{name}'"


# --- Helpers ---

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


class ContextOverflowError(Exception):
    """Raised when the conversation exceeds Gemini's context limit."""
    pass


def _send_with_retry(chat, message, verbose: bool = False):
    """Send a message to Gemini with automatic retry on transient errors."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            return chat.send_message(message)
        except Exception as e:
            error_str = str(e).lower()

            # Context overflow — not retryable
            if any(k in error_str for k in ("400", "token", "context length", "too long", "request too large")):
                raise ContextOverflowError(f"Context overflow: {e}") from e

            is_transient = any(k in error_str for k in ("429", "500", "503", "overloaded", "rate", "unavailable", "deadline", "timeout"))

            if not is_transient or attempt == MAX_RETRIES:
                raise

            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            if verbose:
                print(f"  [retry {attempt + 1}/{MAX_RETRIES}] {type(e).__name__} — waiting {delay}s...")
            log.warning("Transient error (attempt %d/%d): %s. Retrying in %ds...", attempt + 1, MAX_RETRIES, e, delay)
            time.sleep(delay)


# --- Session ---

SESSIONS_DIR = Path(config.get("SPARK_WORKSPACE", "./workspace")) / "sessions"


class Session:
    """A persistent agent session. Maintains chat history across multiple prompts."""

    def __init__(
        self,
        session_id: str | None = None,
        extra_env: dict | None = None,
        cancel_event: threading.Event | None = None,
        pid_callback=None,
    ):
        self.model = config.get("GEMINI_MODEL", "gemini-3-flash-preview")
        self.workspace = config.get("SPARK_WORKSPACE", "./workspace")
        self.max_turns = int(config.get("MAX_TURNS", "30"))
        self.max_cost_usd = float(config.get("MAX_COST_USD", "0.50"))
        self.max_wall_seconds = int(config.get("MAX_WALL_SECONDS", "900"))  # 15 min hard cap per task
        self.extra_env = extra_env or {}
        self.cancel_event = cancel_event
        self.pid_callback = pid_callback

        self.client = genai.Client(api_key=config.get("GOOGLE_API_KEY"))
        self.total_in = 0
        self.total_out = 0
        self.total_turns = 0
        self.total_cost = 0.0
        self.script_executions = []

        # Load existing session or create new one
        if session_id and self._session_file(session_id).exists():
            self.session_id = session_id
            history = self._load_history()
            self.chat = self.client.chats.create(
                model=self.model,
                config=types.GenerateContentConfig(
                    system_instruction=_build_system_prompt(),
                    tools=[TOOL_DECLARATIONS],
                ),
                history=history,
            )
            saved = json.loads(self._session_file(session_id).read_text())
            self.total_in = saved.get("total_input_tokens", 0)
            self.total_out = saved.get("total_output_tokens", 0)
            self.total_turns = saved.get("total_turns", 0)
            self.total_cost = saved.get("total_cost_usd", 0.0)
            self.script_executions = saved.get("script_executions", [])
        else:
            self.session_id = session_id or uuid.uuid4().hex[:8]
            self.chat = self.client.chats.create(
                model=self.model,
                config=types.GenerateContentConfig(
                    system_instruction=_build_system_prompt(),
                    tools=[TOOL_DECLARATIONS],
                ),
            )

    def _session_file(self, sid: str) -> Path:
        return SESSIONS_DIR / f"{sid}.json"

    def _load_history(self) -> list[types.Content]:
        data = json.loads(self._session_file(self.session_id).read_text())
        entries = data.get("history", [])
        for d in entries:
            for part in d.get("parts", []):
                if part.pop("_sig_b64", False):
                    part["thought_signature"] = base64.b64decode(part["thought_signature"])
        return [types.Content(**entry) for entry in entries]

    def _cleanup_scripts(self):
        """Keep scripts — they are needed for experience logging."""
        pass

    def _emit(self, msg):
        """Send log message to stdout and optional callback."""
        print(msg)
        if getattr(self, '_log_cb', None):
            self._log_cb(msg)

    def _log_before(self, name, args):
        """Print what the agent is about to do."""
        if name == "write_file":
            self._emit(f"  Escribiendo {Path(args.get('path', '?')).name}...")
        elif name == "read_file":
            self._emit(f"  Leyendo {Path(args.get('path', '?')).name}...")
        elif name == "execute_bash":
            cmd = args.get("command", "")
            script = next((t for t in cmd.split() if t.endswith(".py")), None)
            print(f"  Ejecutando {script or 'comando'}...", end=" ", flush=True)
            if getattr(self, '_log_cb', None):
                self._log_cb(f"  Ejecutando {script or 'comando'}...")
        else:
            self._emit(f"  {name}...")

    def _log_after(self, name, result):
        """Print the outcome after execution."""
        if name == "execute_bash":
            if "exit_code: 0" in result:
                msg = "OK"
            elif "timed out" in result:
                msg = "timeout!"
            elif "exit_code:" in result:
                errs = [l.strip() for l in result.split("\n") if "Error" in l]
                msg = f"error: {errs[0][:100] if errs else 'fallo'}"
            else:
                msg = ""
            print(msg)
            if getattr(self, '_log_cb', None) and msg:
                self._log_cb(f"    {msg}")

    def _action_label(self, name, args):
        """Short human label of what the agent is about to do (for live progress)."""
        if name == "write_file":
            return f"Escribiendo {Path(args.get('path', '?')).name}"
        if name == "read_file":
            return f"Leyendo {Path(args.get('path', '?')).name}"
        if name == "execute_bash":
            cmd = args.get("command", "")
            script = next((t for t in cmd.split() if t.endswith(".py")), None)
            return f"Ejecutando {script or 'comando'}"
        return name

    def _emit_progress(self, turn, run_in, run_out, action):
        """Report live progress (current turn, accumulated cost, action) to the
        optional progress callback. Best-effort: never let it break the run."""
        cb = getattr(self, "_progress_cb", None)
        if not cb:
            return
        try:
            cb(turn, _calculate_cost(self.model, run_in, run_out), action)
        except Exception:
            pass

    def _dispatch_and_track(self, name, args, execs):
        """Dispatch a tool call and track execute_bash timing."""
        t0 = time.time() if name == "execute_bash" else None
        result = _dispatch(
            name, args, self.workspace, self.extra_env,
            pid_callback=self.pid_callback,
            cancel_event=self.cancel_event,
        )
        # Save last successful .py script for accurate experience logging
        if name == "execute_bash" and "exit_code: 0" in result:
            cmd = args.get("command", "")
            for token in cmd.split():
                if token.endswith(".py"):
                    script_path = Path(self.workspace) / token
                    if script_path.exists():
                        self._last_successful_script = script_path.read_text(encoding="utf-8")
                    break
        if t0 is not None:
            elapsed = round(time.time() - t0, 3)
            exit_code = -1
            if "exit_code: " in result:
                try:
                    exit_code = int(result.rsplit("exit_code: ", 1)[1].strip())
                except (ValueError, IndexError):
                    pass
            elif "timed out" in result:
                exit_code = -2
            execs.append({
                "command": args.get("command", ""),
                "duration_seconds": elapsed,
                "exit_code": exit_code,
                "success": exit_code == 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return result

    def _save(self):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        history_dicts = []
        for content in self.chat._curated_history:
            d = content.model_dump(exclude_none=True)
            for part in d.get("parts", []):
                sig = part.get("thought_signature")
                if isinstance(sig, bytes):
                    part["thought_signature"] = base64.b64encode(sig).decode("ascii")
                    part["_sig_b64"] = True
            history_dicts.append(d)

        data = {
            "session_id": self.session_id,
            "model": self.model,
            "created": datetime.now(timezone.utc).isoformat(),
            "total_turns": self.total_turns,
            "total_input_tokens": self.total_in,
            "total_output_tokens": self.total_out,
            "total_cost_usd": round(self.total_cost, 6),
            "script_executions": self.script_executions,
            "history": history_dicts,
        }
        self._session_file(self.session_id).write_text(json.dumps(data, indent=2, default=str))

    def run(self, prompt: str, verbose: bool = True, log_callback=None,
            progress_callback=None) -> str:
        """Send a prompt to the agent. Chat history persists between calls.

        progress_callback(turn:int, cost_usd:float, action:str) is called before
        each tool dispatch so a caller (e.g. the HTTP server) can surface live
        progress while the run is still in flight.
        """
        self._log_cb = log_callback
        self._progress_cb = progress_callback
        if verbose:
            print(f"\n{'='*60}")
            print(f"Spark [{self.session_id}] — {prompt[:70]}{'...' if len(prompt) > 70 else ''}")
            print(f"{'='*60}\n")

        start = time.time()
        run_in, run_out = 0, 0
        run_execs = []

        try:
            response = _send_with_retry(self.chat, prompt, verbose)
        except ContextOverflowError:
            if verbose:
                print("\n  [STOPPED] Context overflow — conversation too long. Start a new session.")
            self._save()
            return "Error: context overflow. La conversación es demasiado larga. Inicia una nueva sesión."

        inp, out = _extract_usage(response)
        run_in += inp
        run_out += out
        turns = 0
        consecutive_errors = 0
        last_error_sig = None
        stopped_reason = None  # None = normal completion, str = forced stop

        while turns < self.max_turns:
            # Check cost limit
            run_cost_so_far = _calculate_cost(self.model, run_in, run_out)
            if run_cost_so_far >= self.max_cost_usd:
                if verbose:
                    print(f"\n  [STOPPED] Cost limit reached: ${run_cost_so_far:.4f} >= ${self.max_cost_usd:.2f}")
                stopped_reason = "cost_limit"
                break

            # Check wall-clock limit — prevents zombie tasks when stuck investigating API limits
            elapsed = time.time() - start
            if elapsed >= self.max_wall_seconds:
                if verbose:
                    print(f"\n  [STOPPED] Wall-clock limit reached: {elapsed:.0f}s >= {self.max_wall_seconds}s")
                stopped_reason = "wall_timeout"
                break

            # Check external cancel — set by POST /tasks/{id}/cancel
            if self.cancel_event is not None and self.cancel_event.is_set():
                if verbose:
                    print(f"\n  [STOPPED] Cancelled by user")
                stopped_reason = "cancelled"
                break

            calls = _get_function_calls(response)
            if not calls:
                break

            tool_responses = []
            has_error = False
            for fc in calls:
                args = dict(fc.args) if fc.args else {}
                if verbose:
                    self._log_before(fc.name, args)
                self._emit_progress(turns + 1, run_in, run_out,
                                    self._action_label(fc.name, args))
                result = self._dispatch_and_track(fc.name, args, run_execs)
                if verbose:
                    self._log_after(fc.name, result)

                # Track consecutive execution errors
                if fc.name == "execute_bash" and "exit_code: 1" in result:
                    has_error = True
                    # Extract error signature (first line of traceback)
                    error_lines = [l for l in result.split("\n") if "Error" in l or "error" in l.lower()]
                    error_sig = error_lines[0][:100] if error_lines else "unknown"
                    if error_sig == last_error_sig:
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 1
                        last_error_sig = error_sig

                tool_responses.append(
                    types.Part.from_function_response(name=fc.name, response={"result": result})
                )

            # Stop if stuck in an error loop
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                if verbose:
                    print(f"\n  [STOPPED] Same error repeated {consecutive_errors} times. Stopping to avoid wasting turns.")
                tool_responses.append(
                    types.Part.from_function_response(
                        name="execute_bash",
                        response={"result": _FAILURE_SAVE_PROMPT}
                    )
                )

            if not has_error:
                consecutive_errors = 0
                last_error_sig = None

            try:
                response = _send_with_retry(self.chat, tool_responses, verbose)
            except ContextOverflowError:
                if verbose:
                    print("\n  [STOPPED] Context overflow — conversation too long.")
                stopped_reason = "context_overflow"
                break

            inp, out = _extract_usage(response)
            run_in += inp
            run_out += out
            turns += 1

            # After injecting error-loop stop, let the model respond (save failure + report)
            # but then break — no more tool calls after this
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                stopped_reason = "error_loop"
                # Give model extra turns to save the failure experience
                for _ in range(3):
                    calls = _get_function_calls(response)
                    if not calls:
                        break
                    tool_responses = []
                    for fc in calls:
                        args = dict(fc.args) if fc.args else {}
                        if verbose:
                            self._log_before(fc.name, args)
                        result = self._dispatch_and_track(fc.name, args, run_execs)
                        if verbose:
                            self._log_after(fc.name, result)
                        tool_responses.append(
                            types.Part.from_function_response(name=fc.name, response={"result": result})
                        )
                    try:
                        response = _send_with_retry(self.chat, tool_responses, verbose)
                    except ContextOverflowError:
                        break
                    inp, out = _extract_usage(response)
                    run_in += inp
                    run_out += out
                    turns += 1
                break

        # If stopped by max turns, give one last chance to save failure
        if turns >= self.max_turns and stopped_reason is None:
            stopped_reason = "max_turns"

        if stopped_reason in ("cost_limit", "max_turns", "wall_timeout", "cancelled"):
            if verbose:
                print(f"\n  [SAVING FAILURE] Giving model a chance to save what it learned...")
            try:
                response = _send_with_retry(self.chat, _FAILURE_SAVE_PROMPT, verbose)
                inp, out = _extract_usage(response)
                run_in += inp
                run_out += out
                # Let it do write_file calls to save the experience
                for _ in range(3):
                    calls = _get_function_calls(response)
                    if not calls:
                        break
                    tool_responses = []
                    for fc in calls:
                        args = dict(fc.args) if fc.args else {}
                        if verbose:
                            self._log_before(fc.name, args)
                        result = self._dispatch_and_track(fc.name, args, run_execs)
                        if verbose:
                            self._log_after(fc.name, result)
                        tool_responses.append(
                            types.Part.from_function_response(name=fc.name, response={"result": result})
                        )
                    response = _send_with_retry(self.chat, tool_responses, verbose)
                    inp, out = _extract_usage(response)
                    run_in += inp
                    run_out += out
            except Exception:
                pass  # best-effort — don't crash if saving fails

        final_text = _get_text(response)
        duration = time.time() - start
        run_cost = _calculate_cost(self.model, run_in, run_out)

        # Accumulate session totals
        self.total_in += run_in
        self.total_out += run_out
        self.total_turns += turns
        self.total_cost += run_cost
        self.script_executions.extend(run_execs)

        # Save session to disk
        self._save()

        # Clean up intermediate scripts (the final version is saved in learned/)
        self._cleanup_scripts()

        # Save last run stats
        stats = RunStats(
            model=self.model, turns=turns,
            input_tokens=run_in, output_tokens=run_out,
            total_tokens=run_in + run_out, cost_usd=run_cost,
            duration_seconds=round(duration, 2),
            script_executions=run_execs,
        )
        stats_path = Path(self.workspace) / "results" / "_last_run_stats.json"
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(asdict(stats), indent=2))

        if verbose:
            print(f"\n{'='*60}")
            print(f"Spark completed in {turns} turns | {duration:.1f}s")
            print(f"Tokens: {run_in:,} in + {run_out:,} out = {run_in + run_out:,}")
            print(f"Cost: ${run_cost:.6f} | Session total: ${self.total_cost:.6f}")
            if run_execs:
                total_script = sum(e["duration_seconds"] for e in run_execs)
                ok = sum(1 for e in run_execs if e["success"])
                print(f"Scripts: {len(run_execs)} ejecutados ({ok} exitosos) | {total_script:.1f}s total")
            print(f"{'='*60}\n")
            print(final_text)

        return final_text


# --- Convenience function for single-shot usage ---

def run(prompt: str, verbose: bool = True) -> str:
    """Run a single prompt in an ephemeral session."""
    session = Session()
    return session.run(prompt, verbose=verbose)
