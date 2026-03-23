import os

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_TURNS = int(os.getenv("MAX_TURNS", "30"))
WORKSPACE = os.getenv("SPARK_WORKSPACE", "./workspace")
