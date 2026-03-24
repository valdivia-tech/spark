# Spark

Coding agent for DIgSILENT PowerFactory. Takes natural language instructions, writes Python scripts using the PowerFactory API, executes them, and returns structured results.

## Setup

```bash
git clone <repo-url> spark
cd spark
cp .env.example .env   # set your GOOGLE_API_KEY
uv sync
```

## Usage

```bash
# Single command
uv run spark "run a power flow on BD_2030.pfd"

# Interactive mode
uv run spark -i
```

## How it works

Spark is a ReAct agent (Gemini + bash/read/write tools). When you give it an instruction:

1. Writes a Python script
2. Executes it
3. If it fails, fixes and retries
4. Saves results to `workspace/results/*.json`

Each run tracks turns, tokens, cost, and duration in `workspace/results/_last_run_stats.json`.

## Configuration

Set in `.env` or as environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | — | Required. Google AI API key |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite-preview` | Gemini model to use |
| `MAX_TURNS` | `30` | Max agent turns per run |
| `SPARK_WORKSPACE` | `./workspace` | Working directory for scripts and results |

## Project structure

```
spark/
├── spark.py          # CLI entry point
├── agent.py          # ReAct loop (Gemini + tools)
├── config.py         # Environment config
├── prompts/
│   └── system.md     # System prompt with PowerFactory patterns
├── workspace/        # Scripts and results (gitignored)
└── .env              # API keys (gitignored)
```
