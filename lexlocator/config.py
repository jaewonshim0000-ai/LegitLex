"""Environment configuration.

Loads a project-root .env file into os.environ so the server picks up
ANTHROPIC_API_KEY no matter how it's launched (terminal, preview tool, IDE).
Real environment variables always win over .env values.

No third-party dependency — this is a tiny, forgiving .env parser.
"""
from __future__ import annotations
import os
from pathlib import Path


def load_dotenv(path: str | Path | None = None) -> dict:
    """Parse KEY=VALUE lines from .env and set them in os.environ if not
    already present. Returns the dict of values found."""
    if path is None:
        # project root = two levels up from this file (lexlocator/config.py)
        path = Path(__file__).resolve().parent.parent / ".env"
    path = Path(path)
    found: dict[str, str] = {}
    if not path.exists():
        return found
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not key:
            continue
        found[key] = val
        # real env vars take precedence; only fill if missing/empty
        if not os.environ.get(key):
            os.environ[key] = val
    return found


# Load immediately on import.
load_dotenv()
