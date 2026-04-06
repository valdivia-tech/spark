"""Spark HTTP server — wraps the agent for programmatic access."""

import json
import threading
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

import config
from agent import Session, SESSIONS_DIR, LEARNED_DIR, PROMPTS_DIR


# --- Models ---


class TaskRequest(BaseModel):
    prompt: str
    session_id: str | None = None


class TaskResponse(BaseModel):
    task_id: str
    status: Literal["running", "completed", "failed"]
    session_id: str
    result: str | None = None
    error: str | None = None
    stats: dict | None = None
    created: str


# --- Task store ---


@dataclass
class _Task:
    task_id: str
    session_id: str
    status: Literal["running", "completed", "failed"] = "running"
    result: str | None = None
    error: str | None = None
    stats: dict | None = None
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


_tasks: dict[str, _Task] = {}


# --- App ---


@asynccontextmanager
async def _lifespan(app: FastAPI):
    config.load_dotenv()
    yield


app = FastAPI(title="Spark", version="0.1.0", lifespan=_lifespan, redoc_url=None)


# --- UI + Health ---

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    pf_path = config.get("POWERFACTORY_PATH")
    return {
        "status": "ok",
        "powerfactory": bool(pf_path and Path(pf_path).exists()),
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


def _run_task(task: _Task, prompt: str):
    try:
        session = Session(task.session_id or None)
        task.session_id = session.session_id
        result = session.run(prompt, verbose=True)
        task.result = result
        task.status = "completed"
        task.stats = {
            "model": session.model,
            "total_turns": session.total_turns,
            "total_input_tokens": session.total_in,
            "total_output_tokens": session.total_out,
            "total_cost_usd": round(session.total_cost, 6),
            "script_executions": session.script_executions,
        }
    except Exception as e:
        task.error = str(e)
        task.status = "failed"


@app.post("/tasks", status_code=202)
def create_task(req: TaskRequest) -> TaskResponse:
    task = _Task(task_id=uuid.uuid4().hex[:8], session_id=req.session_id or "")
    _tasks[task.task_id] = task
    threading.Thread(target=_run_task, args=(task, req.prompt), daemon=True).start()
    return TaskResponse(**task.__dict__)


@app.get("/tasks")
def list_tasks() -> list[TaskResponse]:
    return [TaskResponse(**t.__dict__) for t in _tasks.values()]


@app.get("/tasks/{task_id}")
def get_task(task_id: str) -> TaskResponse:
    if task_id not in _tasks:
        raise HTTPException(404, "Task not found")
    return TaskResponse(**_tasks[task_id].__dict__)


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
def get_result(name: str) -> dict:
    path = _safe_child(RESULTS_DIR, name, ".json")
    if not path.exists():
        raise HTTPException(404, "Result not found")
    return json.loads(path.read_text(encoding="utf-8"))


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
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=reload)


if __name__ == "__main__":
    main()
