# Spark — Pending Improvements

## Completed

- [x] **Context overflow handling** — Detects 400/context limit errors and stops gracefully instead of crashing.
- [x] **Output truncation** — Tool output truncated to 10K chars to prevent context overflow.
- [x] **Error loop detection** — Stops after 3 consecutive identical errors instead of spinning 30 turns.
- [x] **Project cache** — Uses `results/.project_cache.json` to avoid re-importing .pfd files (was creating 200+ duplicates).
- [x] **Short circuit reference fix** — Corrected attribute names and added Method A (bus faults) vs Method B (line faults).
- [x] **Self-improving skill library (Voyager + ExpeL hybrid)** — Saves experiences (lessons + working script) to `prompts/learned/`. Reads index before new tasks. Learns from both successes and failures.
- [x] **Failure learning** — When a task fails, saves a `[FALLIDO]` experience documenting what didn't work and why. Next attempt reads this and avoids the same dead end.
- [x] **Token budget** — Cost limit per run (MAX_COST_USD) + error loop detection prevents runaway costs.
- [x] **Workspace cleanup** — Auto-deletes intermediate .py scripts after each run. Only results/ and sessions/ persist.

## High Priority

- [ ] **Failure graduation** — When a success experience supersedes a `[FALLIDO]`, automatically mark the failure as resolved in the index. Avoids wasting tokens reading stale failures.
- [ ] **Benchmark suite** — A `benchmark.yaml` with ~10 reference tasks. A script runs them all and reports: pass/fail, turns, cost. Regression testing for prompt/code changes.
- [ ] **Open source readiness** — Add LICENSE (MIT), rewrite README with current features, update pyproject.toml (author, license, repo URL), decide on 7-bus.pfd distribution.

## Medium Priority

- [ ] **Session summarization on context overflow** — Instead of dying, auto-summarize the conversation and start a new session with the summary as context. Enables infinite sessions.
- [ ] **Smart model selection** — Use cheap model (flash-lite) for tasks with existing ✅ experience, expensive model (pro) for new/failed task types. The index already has the info to decide.
- [ ] **Pipeline mode** — Read a CES (PDF), decompose into tasks, execute sequentially (Phase B architecture).
- [ ] **Report generation** — Compile results from multiple simulation runs into a formatted report (docx/pdf).
- [ ] **Logging** — Save a human-readable log per session (`sessions/{id}.log`) with timestamps, prompts, tool calls, results, and errors.

## Low Priority

- [ ] **Server mode** — FastAPI endpoint to receive tasks.
- [ ] **Embedding-based retrieval** — When the skill library grows past ~50 entries, switch from full-index reading to semantic search.
