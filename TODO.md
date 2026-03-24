# Spark — Pending Improvements

## High Priority (before production use)

- [ ] **Context overflow handling** — Detect when chat history exceeds Gemini's context limit (400 error). Auto-start a new session with a summary of what was done, instead of crashing.
- [ ] **Logging** — Save a human-readable log per session (`sessions/{id}.log`) with timestamps, prompts, tool calls, results, and errors. For debugging on the VM.

## Medium Priority (after first real use on VM)

- [x] **Self-improving references (Voyager + ExpeL hybrid)** — After a successful task, Spark saves the experience (lessons learned + working script) to `prompts/learned/`. Before new tasks, reads the index and relevant experiences. Combines Voyager (verified code), ExpeL (distilled lessons from success/failure), and MemGPT (agent-managed memory). Future: embedding-based retrieval when library grows past ~50 entries.
- [ ] **Pipeline mode** — Read a CES (PDF), decompose into tasks, execute sequentially (Phase B architecture from design session).
- [ ] **Report generation** — Compile results from multiple simulation runs into a formatted report (docx/pdf).

## Low Priority (nice to have)

- [ ] **Server mode** — FastAPI endpoint to receive tasks from Teams/Web proxy on Cloud Run.
- [ ] **Token budget** — Set a max cost per session, stop when exceeded.
- [ ] **Workspace cleanup** — Auto-delete old scripts after successful runs, keep only results.
