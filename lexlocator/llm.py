"""LLM client — OpenRouter (OpenAI-compatible) by default.

One key, many models. Set OPENROUTER_API_KEY in .env and (optionally) pick a
model with LEXLOCATOR_MODEL, e.g.:
  openai/gpt-4o-mini            (cheap, supports vision + tools — default)
  anthropic/claude-3.5-sonnet   (strong legal reasoning)
  google/gemini-flash-1.5       (fast, cheap, vision)

Works with plain OpenAI too: set OPENAI_API_KEY and
LEXLOCATOR_BASE_URL=https://api.openai.com/v1 with a model like "gpt-4o-mini".
"""
from __future__ import annotations
import os
import json
from typing import Optional

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

# Default model. Must support function/tool calling; for sign scanning it must
# also support vision. gpt-4o-mini does both and is inexpensive.
DEFAULT_MODEL = os.environ.get("LEXLOCATOR_MODEL", "openai/gpt-4o-mini")

_HEADERS = {
    "HTTP-Referer": "https://lexlocator.local",
    "X-Title": "LexLocator",
}


def _api_key() -> Optional[str]:
    return os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")


def has_api_key() -> bool:
    return bool(_api_key())


def provider_name() -> str:
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "none"


def _base_url() -> str:
    if os.environ.get("LEXLOCATOR_BASE_URL"):
        return os.environ["LEXLOCATOR_BASE_URL"]
    # If only a plain OpenAI key is present, talk to OpenAI directly.
    if not os.environ.get("OPENROUTER_API_KEY") and os.environ.get("OPENAI_API_KEY"):
        return "https://api.openai.com/v1"
    return DEFAULT_BASE_URL


def get_client():
    from openai import OpenAI
    key = _api_key()
    if not key:
        raise RuntimeError("No LLM API key set (OPENROUTER_API_KEY).")
    return OpenAI(base_url=_base_url(), api_key=key, default_headers=_HEADERS)


def _extract_json(text: str) -> dict:
    """Pull the first balanced JSON object out of a model's text reply."""
    if not text:
        return {}
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except ValueError:
            pass
    return {}


def call_tool(system: str, user_content, tool: dict, tool_name: str,
              model: Optional[str] = None, max_tokens: int = 1500) -> dict:
    """Get structured JSON back from the model, robust across providers/models.

    `tool` is an OpenAI function schema: {name, description, parameters}.
    `user_content` may be a string or a list of OpenAI content blocks (vision).

    Strategy:
      1. Native function calling with forced tool_choice (best models).
      2. If that fails or the model ignores it, fall back to JSON-mode prompting
         (works on free/open models like gpt-oss that lack tool support).
    Returns the parsed dict, or {} if nothing usable came back.
    """
    client = get_client()
    mdl = model or DEFAULT_MODEL

    # --- Attempt 1: native tool/function calling ---
    try:
        resp = client.chat.completions.create(
            model=mdl,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            tools=[{"type": "function", "function": tool}],
            tool_choice={"type": "function", "function": {"name": tool_name}},
        )
        msg = resp.choices[0].message
        if getattr(msg, "tool_calls", None):
            try:
                return json.loads(msg.tool_calls[0].function.arguments)
            except (ValueError, TypeError):
                pass
        parsed = _extract_json(getattr(msg, "content", "") or "")
        if parsed:
            return parsed
    except Exception:
        pass  # model/provider may not support tools — fall through

    # --- Attempt 2: JSON-mode prompting (no tools) ---
    schema = json.dumps(tool.get("parameters", {}))
    json_system = (
        system
        + "\n\nReturn ONLY a single JSON object that conforms to this JSON schema. "
        + "No markdown fences, no commentary:\n" + schema
    )
    for use_response_format in (True, False):
        try:
            kwargs = dict(
                model=mdl,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": json_system},
                    {"role": "user", "content": user_content},
                ],
            )
            if use_response_format:
                kwargs["response_format"] = {"type": "json_object"}
            resp = client.chat.completions.create(**kwargs)
            parsed = _extract_json(resp.choices[0].message.content or "")
            if parsed:
                return parsed
        except Exception:
            continue
    return {}
