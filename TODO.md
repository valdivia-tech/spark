# Spark — Pending Improvements

## High Priority (before production use)

- [ ] **Context overflow handling** — Detect when chat history exceeds Gemini's context limit (400 error). Auto-start a new session with a summary of what was done, instead of crashing.
- [ ] **Logging** — Save a human-readable log per session (`sessions/{id}.log`) with timestamps, prompts, tool calls, results, and errors. For debugging on the VM.

## Medium Priority (after first real use on VM)

- [ ] **Self-improving references (Voyager pattern)** — When a PowerFactory script works, save it to `prompts/learned/` with a semantic description. Before writing new scripts, search learned patterns by similarity. Based on Voyager (NVIDIA) skill library approach. See also: Reflexion (save verbal reflections after failures), ExpeL (extract insights from success/failure pairs).
- [ ] **Pipeline mode** — Read a CES (PDF), decompose into tasks, execute sequentially (Phase B architecture from design session).
- [ ] **Report generation** — Compile results from multiple simulation runs into a formatted report (docx/pdf).

## Low Priority (nice to have)

- [ ] **Server mode** — FastAPI endpoint to receive tasks from Teams/Web proxy on Cloud Run.
- [ ] **Token budget** — Set a max cost per session, stop when exceeded.
- [ ] **Workspace cleanup** — Auto-delete old scripts after successful runs, keep only results.
