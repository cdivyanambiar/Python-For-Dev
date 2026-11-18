import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "all-MiniLM-L6-v2"
DOCS_PATH = ROOT / "docs"
DB_PATH = ROOT / "data" / "switches.db"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
