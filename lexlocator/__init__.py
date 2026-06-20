"""LexLocator: hyper-local legal compliance assistant."""
__version__ = "0.1.0"

# Load .env as early as possible so any entry point (server, CLI, scripts)
# sees OPENROUTER_API_KEY.
from . import config  # noqa: E402,F401
