import os
from pathlib import Path

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_TURNS = int(os.getenv("MAX_TURNS", "30"))
WORKSPACE = os.getenv("SPARK_WORKSPACE", "./workspace")


def load_dotenv():
    """Carga variables de .env si existe (sin dependencias externas)."""
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if value and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)

    # Recargar config después de leer .env
    global GOOGLE_API_KEY, GEMINI_MODEL, MAX_TURNS, WORKSPACE
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    MAX_TURNS = int(os.getenv("MAX_TURNS", "30"))
    WORKSPACE = os.getenv("SPARK_WORKSPACE", "./workspace")
