"""Spark HTTP server — wraps the agent for programmatic access."""

import json
import shutil
import subprocess
import threading
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

import config
from agent import Session, SESSIONS_DIR, LEARNED_DIR, PROMPTS_DIR, _kill_process_tree


# --- Models ---


class TaskRequest(BaseModel):
    prompt: str
    session_id: str | None = None


class ResultArtifact(BaseModel):
    """Un archivo de resultado persistido en GCS al completar un task."""

    name: str  # stem, sin extensión
    gcs_uri: str  # gs://bucket/spark-results/{task_id}/{name}.json
    size_bytes: int


class TaskResponse(BaseModel):
    task_id: str
    status: Literal["running", "completed", "failed", "cancelled"]
    session_id: str
    result: str | None = None
    error: str | None = None
    stats: dict | None = None
    result_files: list[str] = []
    result_artifacts: list[ResultArtifact] = []
    created: str
    # Progreso en vivo — actualizado mientras la tarea corre para que el caller
    # (Don Nelson / su frontend) muestre en qué está sin esperar a `stats`.
    current_turn: int = 0
    max_turns: int = 0
    cost_so_far: float = 0.0
    last_action: str | None = None


# --- Task store ---


@dataclass
class _Task:
    task_id: str
    session_id: str
    status: Literal["running", "completed", "failed", "cancelled"] = "running"
    result: str | None = None
    error: str | None = None
    stats: dict | None = None
    result_files: list[str] = field(default_factory=list)
    # Llenado al completar el task si SPARK_RESULTS_BUCKET está configurado.
    # Es la fuente de verdad para auditoría a largo plazo (sobrevive reciclaje
    # de la VM). `result_files` queda para compat — mismos nombres.
    result_artifacts: list[dict] = field(default_factory=list)
    logs: list = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Live progress — updated by the agent's progress_callback while running.
    current_turn: int = 0
    max_turns: int = 0
    cost_so_far: float = 0.0
    last_action: str | None = None
    # Cancellation plumbing — not serialised in TaskResponse (extras are ignored).
    cancel_event: threading.Event = field(default_factory=threading.Event)
    current_pid: int | None = None


_tasks: dict[str, _Task] = {}


# Fields on _Task that exist for plumbing only and must not be exposed in the
# JSON response (Pydantic v2 ignores extras by default but we filter explicitly
# to be future-proof against schema changes and to keep the API surface clean).
_INTERNAL_FIELDS = {"logs", "cancel_event", "current_pid"}


def _to_response(t: _Task) -> TaskResponse:
    return TaskResponse(**{k: v for k, v in t.__dict__.items() if k not in _INTERNAL_FIELDS})


# --- App ---


@asynccontextmanager
async def _lifespan(app: FastAPI):
    config.load_dotenv()
    yield


try:
    _SPARK_VERSION = _pkg_version("spark")
except PackageNotFoundError:
    import tomllib

    with open(Path(__file__).parent / "pyproject.toml", "rb") as _f:
        _SPARK_VERSION = tomllib.load(_f)["project"]["version"]


app = FastAPI(title="Spark", version=_SPARK_VERSION, lifespan=_lifespan, redoc_url=None)


# --- UI + Health ---

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    pf_path = config.get("POWERFACTORY_PATH")
    pf_exists = bool(pf_path and Path(pf_path).exists())
    pf_version = None
    if pf_exists:
        # Extract version from path (e.g. "PowerFactory 2024" → "2024")
        for part in Path(pf_path).parts:
            if "PowerFactory" in part:
                pf_version = part.replace("DIgSILENT", "").strip()
                break
    return {
        "status": "ok",
        "version": app.version,
        "powerfactory": pf_exists,
        "powerfactory_version": pf_version,
        "limits": {
            "max_turns": int(config.get("MAX_TURNS", "30")),
            "max_cost_usd": float(config.get("MAX_COST_USD", "0.50")),
            "max_wall_seconds": int(config.get("MAX_WALL_SECONDS", "900")),
        },
    }


@app.get("/prompt")
def get_prompt() -> PlainTextResponse:
    return PlainTextResponse((PROMPTS_DIR / "system.md").read_text(encoding="utf-8"))


@app.get("/powerfactory")
def get_powerfactory() -> PlainTextResponse:
    return PlainTextResponse((PROMPTS_DIR / "powerfactory.md").read_text(encoding="utf-8"))


# --- Tasks ---


def _safe_child(base: Path, name: str, suffix: str = "") -> Path:
    """Resolve a child path and ensure it stays inside base (prevents path traversal)."""
    path = (base / f"{name}{suffix}").resolve()
    if not path.is_relative_to(base.resolve()):
        raise HTTPException(400, "Invalid path")
    return path


def _upload_task_results_to_gcs(task_id: str, task_results_dir: Path) -> list[dict]:
    """Sube cada .json del directorio a gs://{bucket}/spark-results/{task_id}/.

    Devuelve la lista de artifacts (name, gcs_uri, size_bytes). Si el bucket
    no está configurado o la dep falla, devuelve [] sin romper el task —
    el resultado en disco sigue disponible vía /results/{task_id}/{name}.

    Auth: usa Application Default Credentials. En la VM funciona con
    `gcloud auth application-default login` (no requiere SA JSON).
    """
    bucket_name = config.get("SPARK_RESULTS_BUCKET", "")
    if not bucket_name:
        return []
    try:
        from google.cloud import storage as _gcs_storage
    except ImportError:
        print("[gcs] google-cloud-storage no instalado, skip upload")
        return []

    if not task_results_dir.exists():
        return []

    prefix = config.get("SPARK_RESULTS_GCS_PREFIX", "spark-results").strip("/")

    artifacts: list[dict] = []
    try:
        client = _gcs_storage.Client()
        bucket = client.bucket(bucket_name)
    except Exception as e:
        print(f"[gcs] No pude inicializar cliente GCS ({bucket_name}): {e}")
        return []

    for f in sorted(task_results_dir.glob("*.json")):
        if f.name.startswith("_"):
            continue
        object_path = f"{prefix}/{task_id}/{f.name}"
        try:
            blob = bucket.blob(object_path)
            blob.upload_from_filename(str(f), content_type="application/json")
            artifacts.append(
                {
                    "name": f.stem,
                    "gcs_uri": f"gs://{bucket_name}/{object_path}",
                    "size_bytes": f.stat().st_size,
                }
            )
        except Exception as e:
            # Un archivo que falla no debe abortar el resto: log y seguir.
            print(f"[gcs] Falló subir {object_path}: {e}")

    return artifacts


def _run_task(task: _Task, prompt: str):
    # Create task-specific results directory
    task_results_dir = RESULTS_DIR / task.task_id
    task_results_dir.mkdir(parents=True, exist_ok=True)
    workspace = Path(config.get("SPARK_WORKSPACE", "./workspace"))
    results_rel = str(task_results_dir.relative_to(workspace))

    # Resolve projects dir. Default sits next to the workspace at the repo root
    # (workspace/../projects). Override via SPARK_PROJECTS_DIR for non-default
    # layouts. Always passed as an absolute path so scripts don't need to know
    # their cwd.
    projects_dir = Path(config.get("SPARK_PROJECTS_DIR", str(workspace.parent / "projects"))).resolve()

    def log_cb(msg: str):
        task.logs.append({"ts": datetime.now(timezone.utc).isoformat(), "msg": msg})

    def pid_cb(pid):
        task.current_pid = pid

    def progress_cb(turn: int, cost: float, action: str):
        task.current_turn = turn
        task.cost_so_far = round(cost, 6)
        task.last_action = action
    try:
        session = Session(
            task.session_id or None,
            extra_env={
                "SPARK_RESULTS_DIR": results_rel,
                "SPARK_PROJECTS_DIR": str(projects_dir),
            },
            cancel_event=task.cancel_event,
            pid_callback=pid_cb,
        )
        task.session_id = session.session_id
        task.max_turns = session.max_turns
        result = session.run(
            prompt, verbose=True, log_callback=log_cb, progress_callback=progress_cb
        )
        task.result = result
        # If the cancel flag was set during the run, surface that as the final status.
        if task.cancel_event.is_set():
            task.status = "cancelled"
        else:
            task.status = "completed"
        task.stats = {
            "model": session.model,
            "total_turns": session.total_turns,
            "total_input_tokens": session.total_in,
            "total_output_tokens": session.total_out,
            "total_cost_usd": round(session.total_cost, 6),
            "script_executions": session.script_executions,
        }
        # Collect result files from task-specific directory
        if task_results_dir.exists():
            task.result_files = [
                f.stem for f in sorted(task_results_dir.glob("*.json"))
                if not f.name.startswith("_")
            ]
        # Sincroniza los resultados a GCS (si está configurado) para que
        # sobrevivan al reciclaje de esta VM. No falla el task si GCS falla.
        try:
            task.result_artifacts = _upload_task_results_to_gcs(
                task.task_id, task_results_dir
            )
        except Exception as e:
            print(f"[gcs] upload defensivo falló para {task.task_id}: {e}")
    except Exception as e:
        task.error = str(e)
        task.status = "failed"


@app.post("/tasks", status_code=202)
def create_task(req: TaskRequest) -> TaskResponse:
    task = _Task(task_id=uuid.uuid4().hex[:8], session_id=req.session_id or "")
    _tasks[task.task_id] = task
    threading.Thread(target=_run_task, args=(task, req.prompt), daemon=True).start()
    return _to_response(task)


@app.get("/tasks")
def list_tasks() -> list[TaskResponse]:
    return [_to_response(t) for t in _tasks.values()]


@app.get("/tasks/{task_id}")
def get_task(task_id: str) -> TaskResponse:
    if task_id not in _tasks:
        raise HTTPException(404, "Task not found")
    return _to_response(_tasks[task_id])


@app.get("/tasks/{task_id}/logs")
def get_task_logs(task_id: str) -> list[dict]:
    if task_id not in _tasks:
        raise HTTPException(404, "Task not found")
    return _tasks[task_id].logs


@app.post("/tasks/{task_id}/cancel", status_code=202)
def cancel_task(task_id: str) -> TaskResponse:
    """Force-cancel a running task: kill its current subprocess tree and signal
    the agent loop to exit cleanly at its next iteration.

    Idempotent: cancelling a task that already finished returns its current
    state unchanged. The agent's failure-save hook still runs, so a [FALLIDO]
    experience is logged even on user cancel.
    """
    if task_id not in _tasks:
        raise HTTPException(404, "Task not found")
    t = _tasks[task_id]
    if t.status != "running":
        return _to_response(t)

    # 1) Signal the agent loop. If it's between iterations it'll catch this on
    #    the next pass and exit through the failure-save path.
    t.cancel_event.set()

    # 2) Kill the currently-running subprocess tree, if any. This unblocks the
    #    agent thread which is waiting on Popen.communicate(). The thread then
    #    sees cancel_event set and returns "error: cancelled by user", and the
    #    next loop iteration breaks with stopped_reason="cancelled".
    pid = t.current_pid
    if pid is not None:
        try:
            _kill_process_tree(pid)
        except Exception:
            pass

    return _to_response(t)


# --- Workspace inspection ---
#
# Exposes Spark's workspace (scripts, results, anything Spark wrote) so callers
# can audit the actual code/data that ran. Useful for catching API gotchas
# (`obj.m:loading` vs `obj.GetAttribute('m:loading')`) BEFORE the next iteration
# and for general post-mortem of failures.

WORKSPACE_DIR = Path(config.get("SPARK_WORKSPACE", "./workspace")).resolve()


def _safe_workspace_path(rel_path: str) -> Path:
    """Resolve a relative path inside the workspace, blocking traversal."""
    target = (WORKSPACE_DIR / rel_path).resolve()
    if not target.is_relative_to(WORKSPACE_DIR):
        raise HTTPException(400, "Path escapes workspace")
    return target


@app.get("/workspace")
def list_workspace_root() -> dict:
    """List entries at the workspace root."""
    if not WORKSPACE_DIR.exists():
        return {"path": "", "entries": []}
    entries = [
        {"name": p.name, "type": "dir" if p.is_dir() else "file", "size": p.stat().st_size if p.is_file() else None}
        for p in sorted(WORKSPACE_DIR.iterdir())
    ]
    return {"path": "", "entries": entries}


@app.get("/workspace/{path:path}")
def get_workspace_entry(path: str):
    """Return a workspace file's content (plain text) or a directory listing.

    Examples (assuming Spark workspace at ./workspace):
        GET /workspace/extract_cen_2604.py     → script content
        GET /workspace/results                 → directory listing
        GET /workspace/results/<task>/<file>   → result file content
    """
    target = _safe_workspace_path(path)
    if not target.exists():
        raise HTTPException(404, "Not found")
    if target.is_dir():
        entries = [
            {"name": p.name, "type": "dir" if p.is_dir() else "file", "size": p.stat().st_size if p.is_file() else None}
            for p in sorted(target.iterdir())
        ]
        return {"path": path, "entries": entries}
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(415, "Binary file — fetch directly if needed")
    return PlainTextResponse(text)


@app.delete("/workspace/{path:path}")
def delete_workspace_entry(path: str) -> dict:
    """Delete a workspace file or directory (recursive for dirs).

    Used for housekeeping when stale scripts/results from prior sessions
    pollute the workspace and cause the agent to read the wrong files.
    Path traversal is blocked by `_safe_workspace_path`. Refuses to delete
    the workspace root itself.
    """
    target = _safe_workspace_path(path)
    if target == WORKSPACE_DIR:
        raise HTTPException(400, "Refusing to delete workspace root")
    if not target.exists():
        raise HTTPException(404, "Not found")
    if target.is_dir():
        shutil.rmtree(target)
        return {"deleted": path, "type": "dir"}
    target.unlink()
    return {"deleted": path, "type": "file"}


# --- Admin / state reset ---
#
# PowerFactory persists imported projects across Python subprocess invocations
# (the user database lives in the PF process). Over a long catalog run, modified
# generators, loads, shunts, etc. accumulate on the same imported project,
# eventually putting PF into a state where new tasks hang or crash. This
# endpoint nukes all imported IntPrj objects from the user, restoring the
# baseline. The runner calls it between catalog tasks.

_RESET_SCRIPT = '''
import sys, os
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\\\\Program Files\\\\DIgSILENT\\\\PowerFactory 2024 SP1\\\\Python\\\\3.12")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)
pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')
import powerfactory
try:
    app = powerfactory.GetApplicationExt()
except powerfactory.ExitError:
    app = powerfactory.GetApplication()
user = app.GetCurrentUser()
deleted = []
for prj in (user.GetContents("*.IntPrj") or []):
    name = prj.loc_name
    try:
        prj.Delete()
        deleted.append(name)
    except Exception as e:
        print(f"FAILED to delete {name}: {e}")
print("DELETED:", deleted)
'''


# --- Projects (pre-stage .pfd from GCS into SPARK_PROJECTS_DIR) ---


class PullGcsRequest(BaseModel):
    gcs_uri: str  # gs://<bucket>/<object>
    name: str | None = None  # opcional: nombre local de destino (sin path, debe terminar en .pfd)


class PullGcsResponse(BaseModel):
    filename: str
    local_path: str
    size_bytes: int
    pulled_at: str
    skipped_existing: bool


def _parse_gcs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise HTTPException(400, "URI must start with gs://")
    rest = uri[5:]
    if "/" not in rest:
        raise HTTPException(400, "URI must be gs://<bucket>/<object>")
    bucket, blob = rest.split("/", 1)
    if not bucket or not blob:
        raise HTTPException(400, "URI must be gs://<bucket>/<object>")
    return bucket, blob


def _resolve_projects_dir() -> Path:
    """Resuelve SPARK_PROJECTS_DIR igual que _run_task — workspace/../projects por default."""
    workspace = Path(config.get("SPARK_WORKSPACE", "./workspace"))
    return Path(config.get("SPARK_PROJECTS_DIR", str(workspace.parent / "projects"))).resolve()


@app.post("/projects/pull-gcs")
def pull_project_from_gcs(req: PullGcsRequest) -> PullGcsResponse:
    """Descarga un .pfd desde GCS a SPARK_PROJECTS_DIR.

    Pensado para que un orquestador (ej. Don Nelson) pre-stagee la base
    PowerFactory antes de mandar un POST /tasks que la consuma. La descarga
    es idempotente: si el archivo ya existe localmente con el mismo tamaño
    que el blob remoto, se reusa.
    """
    # Lazy import: google-cloud-storage es dep opcional del extra `server`.
    try:
        from google.cloud import storage as _gcs_storage
    except ImportError:
        raise HTTPException(
            500,
            "google-cloud-storage no está instalado. Instalá con `pip install -e .[server]` o `uv sync`.",
        )

    bucket_name, blob_path = _parse_gcs_uri(req.gcs_uri)

    filename = req.name if req.name else Path(blob_path).name
    if not filename.lower().endswith(".pfd"):
        raise HTTPException(400, "El nombre local debe terminar en .pfd")
    if "/" in filename or "\\" in filename or filename in (".", ".."):
        raise HTTPException(400, "Nombre local inválido (sin paths)")

    projects_dir = _resolve_projects_dir()
    projects_dir.mkdir(parents=True, exist_ok=True)
    target = (projects_dir / filename).resolve()
    if not target.is_relative_to(projects_dir):
        raise HTTPException(400, "Path traversal detectado")

    client = _gcs_storage.Client()
    blob = client.bucket(bucket_name).blob(blob_path)
    if not blob.exists():
        raise HTTPException(404, f"Object not found: {req.gcs_uri}")
    blob.reload()
    remote_size = blob.size or 0

    skipped = target.exists() and target.stat().st_size == remote_size
    if not skipped:
        blob.download_to_filename(str(target))

    return PullGcsResponse(
        filename=filename,
        local_path=str(target),
        size_bytes=target.stat().st_size,
        pulled_at=datetime.now(timezone.utc).isoformat(),
        skipped_existing=skipped,
    )


# --- Admin ---


@app.post("/admin/reset-projects")
def reset_projects() -> dict:
    """Delete all IntPrj objects from the PF user's database. Returns deleted list.

    Synchronous and bypasses the agent loop. Used by the catalog runner between
    tasks to prevent cumulative model corruption.
    """
    try:
        proc = subprocess.run(
            ["python", "-c", _RESET_SCRIPT],
            cwd=str(WORKSPACE_DIR),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Reset script timed out (60s) — PowerFactory likely hung; restart Spark")
    if proc.returncode != 0:
        raise HTTPException(500, f"Reset failed (exit {proc.returncode}): stderr={proc.stderr[:500]}")
    deleted = []
    for line in proc.stdout.splitlines():
        if line.startswith("DELETED:"):
            try:
                deleted = json.loads(line.split(":", 1)[1].strip().replace("'", '"'))
            except Exception:
                deleted = [line.split(":", 1)[1].strip()]
    return {"deleted": deleted, "stdout": proc.stdout[-1000:]}


# --- Sessions ---


@app.get("/sessions")
def list_sessions() -> list[dict]:
    if not SESSIONS_DIR.exists():
        return []
    sessions = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            execs = data.get("script_executions", [])
            sessions.append({
                "session_id": data.get("session_id", f.stem),
                "model": data.get("model"),
                "total_turns": data.get("total_turns", 0),
                "total_cost_usd": data.get("total_cost_usd", 0),
                "created": data.get("created", ""),
                "script_exec_count": len(execs),
                "script_exec_seconds": round(sum(e.get("duration_seconds", 0) for e in execs), 3),
            })
        except Exception:
            continue
    return sessions


@app.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    path = _safe_child(SESSIONS_DIR, session_id, ".json")
    if not path.exists():
        raise HTTPException(404, "Session not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("history", None)
    return data


# --- Results ---

RESULTS_DIR = Path(config.get("SPARK_WORKSPACE", "./workspace")) / "results"


@app.get("/results")
def list_results() -> list[dict]:
    """List all result files with their timing data."""
    if not RESULTS_DIR.exists():
        return []
    results = []
    for f in sorted(RESULTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.name.startswith("_"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "name": f.stem,
                "timing": data.get("timing"),
                "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
        except Exception:
            continue
    return results


@app.get("/results/{name}")
def get_result(name: str):
    path = _safe_child(RESULTS_DIR, name, ".json")
    if not path.exists():
        raise HTTPException(404, "Result not found")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/results/{task_id}/{name}")
def get_task_result(task_id: str, name: str):
    """Get a result file from a specific task's results directory."""
    task_dir = _safe_child(RESULTS_DIR, task_id)
    if not task_dir.is_dir():
        raise HTTPException(404, "Task results not found")
    path = _safe_child(task_dir, name, ".json")
    if not path.exists():
        raise HTTPException(404, f"Result '{name}' not found in task {task_id}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(422, f"Result '{name}' in task {task_id} contains invalid JSON")


# --- Script executions ---


@app.get("/script-executions")
def list_script_executions() -> list[dict]:
    """All script executions across sessions, most recent first."""
    if not SESSIONS_DIR.exists():
        return []
    all_execs = []
    for f in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sid = data.get("session_id", f.stem)
            for e in data.get("script_executions", []):
                all_execs.append({**e, "session_id": sid})
        except Exception:
            continue
    all_execs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return all_execs


# --- Learned experiences ---


@app.get("/learned")
def list_learned() -> list[dict]:
    index = LEARNED_DIR / "index.md"
    if not index.exists():
        return []
    entries = []
    for line in index.read_text(encoding="utf-8").splitlines():
        if not (line.startswith("|") and "`" in line):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) >= 2:
            slug = cols[0].strip("`").removesuffix(".md")
            entries.append({
                "slug": slug,
                "description": cols[1],
                "failed": "FALLIDO" in line,
            })
    return entries


@app.get("/learned/{slug}")
def get_learned(slug: str) -> PlainTextResponse:
    path = _safe_child(LEARNED_DIR, slug, ".md")
    if not path.exists():
        raise HTTPException(404, "Experience not found")
    return PlainTextResponse(path.read_text(encoding="utf-8"))


# --- Entry point ---


def main():
    import uvicorn
    port = int(config.get("PORT", "8001"))
    reload = config.get("RELOAD", "").lower() in ("1", "true")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=reload,
                log_level="warning")


if __name__ == "__main__":
    main()
