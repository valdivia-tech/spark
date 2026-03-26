# Spark — Pending Improvements

## High Priority (before production use)

- [x] **Context overflow handling** — Detects 400/context limit errors and stops gracefully instead of crashing.
- [x] **Output truncation** — Tool output truncated to 10K chars to prevent context overflow.
- [x] **Error loop detection** — Stops after 3 consecutive identical errors instead of spinning 30 turns.
- [x] **Project cache** — Uses `results/.project_cache.json` to avoid re-importing .pfd files (was creating 200+ duplicates).
- [x] **Short circuit reference fix** — Corrected attribute names and added Method A (bus faults) vs Method B (line faults).
- [ ] **Logging** — Save a human-readable log per session (`sessions/{id}.log`) with timestamps, prompts, tool calls, results, and errors. For debugging on the VM.

## Medium Priority (after first real use on VM)

- [x] **Self-improving references (Voyager + ExpeL hybrid)** — After a successful task, Spark saves the experience (lessons learned + working script) to `prompts/learned/`. Before new tasks, reads the index and relevant experiences. Combines Voyager (verified code), ExpeL (distilled lessons from success/failure), and MemGPT (agent-managed memory). Future: embedding-based retrieval when library grows past ~50 entries.
- [ ] **Pipeline mode** — Read a CES (PDF), decompose into tasks, execute sequentially (Phase B architecture from design session).
- [ ] **Report generation** — Compile results from multiple simulation runs into a formatted report (docx/pdf).

## Low Priority (nice to have)

- [ ] **Server mode** — FastAPI endpoint to receive tasks from Teams/Web proxy on Cloud Run.
- [x] **Token budget** — Cost limit per run (MAX_COST_USD) already implemented + error loop detection prevents runaway costs.
- [ ] **Workspace cleanup** — Auto-delete old scripts after successful runs, keep only results.
