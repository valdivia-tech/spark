# Contributing to Spark

Thanks for your interest in contributing to Spark! This guide will help you get started.

## Getting started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/<your-username>/spark.git
   cd spark
   ```
3. Set up the environment:
   ```bash
   cp .env.example .env   # add your GOOGLE_API_KEY
   uv sync
   ```
4. Create a branch for your work:
   ```bash
   git checkout -b my-feature
   ```

## What you can contribute

- **New learned experiences** -- If you've used Spark with PowerFactory and found non-obvious patterns, add them to `prompts/learned/`
- **Bug fixes** -- Found a crash or incorrect behavior? PRs welcome
- **Prompt improvements** -- Better system prompts lead to better scripts. Changes to `prompts/system.md` or `prompts/powerfactory.md` are valuable
- **Tool improvements** -- Improvements to the ReAct loop, error handling, or tool dispatch in `agent.py`
- **LLM providers** -- Spark currently uses Gemini, but adding support for other LLMs (Claude, OpenAI, local models via Ollama, etc.) is welcome. If you're adding a new provider, keep the same tool interface so the ReAct loop works unchanged
- **Documentation** -- Clearer README, usage examples, or guides

## Project structure

```
spark.py        # CLI entry point
agent.py        # ReAct agent loop (Session class, tool dispatch)
config.py       # Environment config loader
prompts/
  system.md     # System prompt
  powerfactory.md # PowerFactory API reference
  learned/      # Self-improving experience library
```

## Guidelines

- **Keep it simple.** Spark is intentionally minimal. Don't add abstractions for hypothetical future needs.
- **Test with real PowerFactory projects** when possible. The agent's value is in producing correct scripts, not in passing mocked tests.
- **Write clear commit messages.** Follow the existing style: `fix:`, `feat:`, `docs:` prefixes.
- **Spanish is fine** in learned experiences and user-facing prompts. Code and comments should be in English.

## Submitting a PR

1. Make sure your changes work (`uv run spark "your test prompt"`)
2. Keep PRs focused -- one feature or fix per PR
3. Describe what you changed and why in the PR description
4. If you're adding a learned experience, include the task that produced it

## Reporting issues

Open an issue on GitHub with:
- What you tried to do
- What happened instead
- Your PowerFactory version (if relevant)
- The Spark session log (if available, from `workspace/sessions/`)

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
