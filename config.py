import os
from pathlib import Path

_ROOT = Path(__file__).parent


def load_dotenv():
    """Load .env file if it exists (no external dependencies)."""
    env_file = _ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def get(key: str, default: str = "") -> str:
    return os.getenv(key, default)
