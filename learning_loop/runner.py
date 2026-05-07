"""Learning loop runner — drives Spark through the catalog, measures turns to first-try success.

Runs locally on the user's machine. Talks to Spark over HTTP.
Persists state in progress.json. Notifies via stdout (and optionally external hooks).
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).parent
CATALOG = HERE / "catalog.yaml"
PROGRESS = HERE / "progress.json"
RESULTS_DIR = HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

DEFAULT_SPARK = "http://34.176.224.119:8001"
DEFAULT_PF_VERSION = "2024-sp1"


def http_get(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post(url: str, body: dict, timeout: int = 30) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def load_progress() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    return {"runs": [], "totals": {"cost_usd": 0.0, "tasks_attempted": 0}, "started": _now_iso()}


def save_progress(p: dict) -> None:
    PROGRESS.write_text(json.dumps(p, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_prompt(task: dict, params: dict, system: dict, pf_version: str) -> str:
    """Compose the prompt sent to Spark from catalog task + test params + system reference."""
    pfd = system["pfd"]
    pfd_filename = os.path.basename(pfd)
    sys_name = system["name"]
    base = task["prompt"].strip()
    hints = task.get("hints", []) or []
    parts = [
        f"# Task: {task['name']}",
        f"# Target system: {sys_name}",
        f"# PowerFactory .pfd filename: {pfd_filename}  (load via os.path.join(os.environ['SPARK_PROJECTS_DIR'], '{pfd_filename}'))",
        f"# PowerFactory version: {pf_version}",
        "",
        base,
    ]
    if params:
        parts += ["", "Parameters for this run:", json.dumps(params, indent=2)]
    if hints:
        parts += ["", "Hints (from catalog):", *(f"- {h}" for h in hints)]
    parts += [
        "",
        "Return your JSON results to the SPARK_RESULTS_DIR. Always include timing.",
    ]
    return "\n".join(parts)


def submit_and_wait(spark_url: str, prompt: str, poll_interval: int = 10, max_wait: int = 1100) -> dict:
    """Submit a task and poll until it reaches a terminal state.

    max_wait is intentionally larger than Spark's MAX_WALL_SECONDS (default
    900s) so Spark's own wall cap fires first and returns a terminal status
    before we give up. If we DO time out anyway (Spark hung), we cancel the
    task explicitly before returning — leaving zombie tasks running causes
    the next task to run concurrently with the zombie, which crashes
    PowerFactory (single-instance) with ExitError 7000.
    """
    submit = http_post(f"{spark_url}/tasks", {"prompt": prompt})
    task_id = submit["task_id"]
    started = time.monotonic()
    last_status = None
    while True:
        try:
            status = http_get(f"{spark_url}/tasks/{task_id}", timeout=15)
        except urllib.error.URLError as e:
            print(f"  (poll error: {e}) — retrying", flush=True)
            time.sleep(poll_interval)
            continue
        st = status.get("status")
        if st != last_status:
            print(f"  [{task_id[:8]}] status={st}", flush=True)
            last_status = st
        if st in ("completed", "failed", "cancelled"):
            return status
        if time.monotonic() - started > max_wait:
            print(f"  [{task_id[:8]}] poll timeout — cancelling to prevent zombie", flush=True)
            try:
                http_post(f"{spark_url}/tasks/{task_id}/cancel", {}, timeout=15)
            except Exception as e:
                print(f"    cancel call failed: {e}", flush=True)
            # Give Spark up to 30s to actually cancel before returning.
            for _ in range(15):
                time.sleep(2)
                try:
                    final = http_get(f"{spark_url}/tasks/{task_id}", timeout=15)
                    if final.get("status") in ("completed", "failed", "cancelled"):
                        return {**final, "status": final.get("status") or "timeout"}
                except urllib.error.URLError:
                    pass
            return {**status, "status": "timeout"}
        time.sleep(poll_interval)


def fetch_result_file(spark_url: str, task_id: str, name: str) -> dict | None:
    try:
        return http_get(f"{spark_url}/results/{task_id}/{name}", timeout=20)
    except Exception:
        return None


def run_one(spark_url: str, task: dict, params: dict, system: dict, pf_version: str) -> dict:
    prompt = build_prompt(task, params, system, pf_version)
    print(f"\n=== {task['name']} on {system['name']} | params={params} ===", flush=True)
    t0 = time.monotonic()
    result = submit_and_wait(spark_url, prompt)
    elapsed = time.monotonic() - t0

    stats = result.get("stats") or {}
    files = result.get("result_files") or []
    fetched = {}
    for fn in files:
        data = fetch_result_file(spark_url, result["task_id"], fn)
        if data is not None:
            fetched[fn] = data

    # Detect Pro hiccups: agent returned without ever executing a script.
    # Spark marks these "completed" because the model stopped emitting
    # function calls, but no work was actually done. We override to
    # "no_op_failure" so the catalog round doesn't conflate empty turns
    # with real successes (and so optimize_log shows the regression).
    spark_status = result.get("status")
    if spark_status == "completed" and not stats.get("script_executions"):
        spark_status = "no_op_failure"

    summary = {
        "task": task["name"],
        "system": system["name"],
        "params": params,
        "pf_version": pf_version,
        "task_id": result.get("task_id"),
        "session_id": result.get("session_id"),
        "status": spark_status,
        "wall_seconds": round(elapsed, 1),
        "stats": stats,
        "result_text": (result.get("result") or "")[:2000],
        "error": result.get("error"),
        "result_files": files,
        "results_data": fetched,
        "timestamp": _now_iso(),
    }
    return summary


def _slug(task_name: str, params: dict) -> str:
    if not params:
        return task_name
    def safe(v):
        return str(v).replace("/", "-").replace("\\", "-").replace(" ", "_").replace(":", "-")
    suffix = "_".join(f"{k}-{safe(v)}" for k, v in sorted(params.items()))
    return f"{task_name}__{suffix}"


def _record_run(progress: dict, summary: dict) -> Path:
    progress["runs"].append(summary)
    progress["totals"]["tasks_attempted"] += 1
    cost = (summary.get("stats") or {}).get("total_cost_usd") or 0.0
    progress["totals"]["cost_usd"] = round(progress["totals"]["cost_usd"] + cost, 4)
    save_progress(progress)
    out_path = RESULTS_DIR / f"{summary['timestamp'].replace(':', '-')}_{_slug(summary['task'], summary['params'])}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return out_path


def cmd_discover(args):
    """Run every (task, params) pair in the requested tiers once. Save results."""
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    sys_choice = catalog["systems"][args.system]
    tiers = args.tiers.split(",")

    progress = load_progress()
    started_cost = progress["totals"]["cost_usd"]
    cap = args.cost_cap

    pending = []
    for tier in tiers:
        for task in catalog.get(tier, []) or []:
            for params in (task.get("test_params") or [{}]):
                pending.append((tier, task, params))

    print(f"Discover: {len(pending)} (task, params) pairs queued. Cap=${cap}.", flush=True)

    for i, (tier, task, params) in enumerate(pending, 1):
        slug = _slug(task["name"], params)
        if (HERE / "golden" / f"{slug}.json").exists() and not args.redo:
            print(f"[{i}/{len(pending)}] SKIP {tier}/{slug} (golden exists)", flush=True)
            continue
        spent = progress["totals"]["cost_usd"] - started_cost
        if spent >= cap:
            print(f"[{i}/{len(pending)}] STOP: cost cap reached (${spent:.2f} >= ${cap})", flush=True)
            return
        print(f"[{i}/{len(pending)}] RUN  {tier}/{slug}  (spent so far: ${spent:.2f})", flush=True)
        try:
            summary = run_one(args.spark, task, params, sys_choice, args.pf_version)
        except Exception as e:
            print(f"  EXCEPTION: {e}", flush=True)
            continue
        out_path = _record_run(progress, summary)
        stats = summary.get("stats") or {}
        print(f"  -> {summary['status']} | turns={stats.get('total_turns')} cost=${stats.get('total_cost_usd', 0):.4f} wall={summary['wall_seconds']}s", flush=True)
        print(f"     saved: {out_path.name}", flush=True)


def cmd_optimize(args):
    """Re-run goldened tasks N rounds. Measure turn count progression per (task, params)."""
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    sys_choice = catalog["systems"][args.system]
    golden_dir = HERE / "golden"
    optimize_log = HERE / "optimize_log.json"

    # Build a task lookup: name -> task dict (catalog)
    task_lookup = {}
    for tier_name in [k for k in catalog if k.startswith("tier_")]:
        for t in catalog.get(tier_name, []) or []:
            task_lookup[t["name"]] = t

    # Load all goldens
    goldens = []
    for gf in sorted(golden_dir.glob("*.json")):
        g = json.loads(gf.read_text())
        if g.get("pf_version") != args.pf_version:
            continue
        if g["task"] not in task_lookup:
            print(f"WARN: golden {gf.name} references unknown task {g['task']}, skipping")
            continue
        goldens.append((gf.name, g))

    # Filter by --only if provided
    if args.only:
        wanted = set(args.only.split(","))
        goldens = [(n, g) for (n, g) in goldens if g["task"] in wanted]

    print(f"Optimize: {len(goldens)} goldened tasks × {args.rounds} rounds = {len(goldens)*args.rounds} runs", flush=True)

    log = json.loads(optimize_log.read_text()) if optimize_log.exists() else {"runs": []}
    progress = load_progress()
    started_cost = progress["totals"]["cost_usd"]

    for round_num in range(1, args.rounds + 1):
        print(f"\n========== ROUND {round_num} ==========", flush=True)
        for gname, g in goldens:
            spent = progress["totals"]["cost_usd"] - started_cost
            if spent >= args.cost_cap:
                print(f"STOP: cost cap reached (${spent:.2f})", flush=True)
                _write_optimize_log(optimize_log, log)
                return
            # Reset PowerFactory state before every task to prevent the model
            # state from previous tasks (modified gens/loads/shunts, accumulated
            # study-case objects) from corrupting this run. Best-effort: if
            # reset fails, log it but continue — the task may still succeed,
            # and a successful task is better than no task.
            try:
                resp = http_post(f"{args.spark}/admin/reset-projects", {}, timeout=90)
                deleted = resp.get("deleted") or []
                if deleted:
                    print(f"  reset: deleted {deleted}", flush=True)
            except Exception as e:
                print(f"  reset failed (continuing): {e}", flush=True)
            task = task_lookup[g["task"]]
            params = g.get("params") or {}
            print(f"  [round {round_num}] {g['task']} {params}", flush=True)
            try:
                summary = run_one(args.spark, task, params, sys_choice, args.pf_version)
            except Exception as e:
                print(f"    EXCEPTION: {e}", flush=True)
                continue
            # Record into progress
            _record_run(progress, summary)
            stats = summary.get("stats") or {}
            log["runs"].append({
                "round": round_num,
                "task": g["task"],
                "params": params,
                "turns": stats.get("total_turns"),
                "cost_usd": stats.get("total_cost_usd"),
                "wall_seconds": summary.get("wall_seconds"),
                "status": summary.get("status"),
                "task_id": summary.get("task_id"),
                "timestamp": summary.get("timestamp"),
            })
            _write_optimize_log(optimize_log, log)
            print(f"    -> turns={stats.get('total_turns')} cost=${stats.get('total_cost_usd', 0):.4f} wall={summary.get('wall_seconds')}s", flush=True)

    print(f"\nDone. Spent ${progress['totals']['cost_usd'] - started_cost:.2f} across {len(goldens)*args.rounds} runs", flush=True)


def _write_optimize_log(path: Path, log: dict) -> None:
    path.write_text(json.dumps(log, indent=2), encoding="utf-8")


def cmd_smoke(args):
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    systems = catalog["systems"]
    sys_choice = systems[args.system]

    tier_tasks = catalog.get(args.tier, [])
    task = next((t for t in tier_tasks if t["name"] == args.task), None)
    if not task:
        print(f"Task {args.task} not found in {args.tier}")
        sys.exit(1)
    params = json.loads(args.params) if args.params else (task.get("test_params") or [{}])[0]

    progress = load_progress()
    summary = run_one(args.spark, task, params, sys_choice, args.pf_version)
    progress["runs"].append(summary)
    progress["totals"]["tasks_attempted"] += 1
    cost = (summary.get("stats") or {}).get("total_cost_usd") or 0.0
    progress["totals"]["cost_usd"] = round(progress["totals"]["cost_usd"] + cost, 4)
    save_progress(progress)

    out_path = RESULTS_DIR / f"{summary['timestamp'].replace(':', '-')}_{task['name']}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSaved: {out_path}")
    print(f"Status: {summary['status']}  turns: {(stats := summary.get('stats') or {}).get('turns')}  cost: ${stats.get('total_cost_usd', 0):.4f}  wall: {summary['wall_seconds']}s")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--spark", default=DEFAULT_SPARK)
    p.add_argument("--pf-version", default=DEFAULT_PF_VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)

    disc = sub.add_parser("discover", help="Run all variants of selected tiers once on a system")
    disc.add_argument("--tiers", default="tier_0,tier_1", help="Comma-separated tier names")
    disc.add_argument("--system", default="small", choices=["small", "big"])
    disc.add_argument("--cost-cap", type=float, default=20.0, help="USD spent in this discover run before stopping")
    disc.add_argument("--redo", action="store_true", help="Re-run even if golden already exists")
    disc.set_defaults(func=cmd_discover)

    opt = sub.add_parser("optimize", help="Re-run all goldened tasks N rounds, measure turn progression")
    opt.add_argument("--rounds", type=int, default=3)
    opt.add_argument("--system", default="small", choices=["small", "big"])
    opt.add_argument("--cost-cap", type=float, default=15.0)
    opt.add_argument("--only", default=None, help="Comma-separated task names to limit scope")
    opt.set_defaults(func=cmd_optimize)

    smoke = sub.add_parser("smoke", help="Run a single task once")
    smoke.add_argument("--tier", default="tier_0")
    smoke.add_argument("--task", required=True)
    smoke.add_argument("--system", default="small", choices=["small", "big"])
    smoke.add_argument("--params", default=None, help="JSON params override")
    smoke.set_defaults(func=cmd_smoke)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
