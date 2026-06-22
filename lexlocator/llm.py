"""LLM client — Claude (Anthropic) preferred, OpenRouter as fallback.

If ANTHROPIC_API_KEY is set, every call goes to Claude via the official
`anthropic` SDK — native tool use (clean structured output) and native vision
(sign scanning + complaint photos). Otherwise it falls back to the
OpenAI-compatible OpenRouter path.

Model: set LEXLOCATOR_MODEL. For Claude, use one of:
  claude-haiku-4-5    (cheapest + fast, has vision — good default for this app)
  claude-sonnet-4-6   (stronger reasoning)
  claude-opus-4-8     (most capable)
If LEXLOCATOR_MODEL isn't a Claude model (e.g. a leftover OpenRouter id), the
Claude path ignores it and uses claude-opus-4-8.
"""
from __future__ import annotations
import os
import json
from typing import Optional

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
ANTHROPIC_DEFAULT_MODEL = "claude-opus-4-8"

_HEADERS = {
    "HTTP-Referer": "https://lexlocator.local",
    "X-Title": "LexLocator",
}


# ---------------------------------------------------------------------------
# Provider / key detection
# ---------------------------------------------------------------------------

def _anthropic_key() -> Optional[str]:
    return os.environ.get("ANTHROPIC_API_KEY")


def _openai_key() -> Optional[str]:
    return os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")


def has_api_key() -> bool:
    return bool(_anthropic_key() or _openai_key())


def provider_name() -> str:
    if _anthropic_key():
        return "anthropic"
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "none"


def _anthropic_model(model: Optional[str]) -> str:
    m = model or os.environ.get("LEXLOCATOR_MODEL", "")
    return m if m.startswith("claude") else ANTHROPIC_DEFAULT_MODEL


# The model shown in /api/health and used as the default. Reflects the active
# provider so the UI shows what's really answering.
if _anthropic_key():
    DEFAULT_MODEL = _anthropic_model(None)
else:
    DEFAULT_MODEL = os.environ.get("LEXLOCATOR_MODEL", "openai/gpt-4o-mini")


# ---------------------------------------------------------------------------
# OpenAI-compatible (OpenRouter) plumbing
# ---------------------------------------------------------------------------

def _base_url() -> str:
    if os.environ.get("LEXLOCATOR_BASE_URL"):
        return os.environ["LEXLOCATOR_BASE_URL"]
    if not os.environ.get("OPENROUTER_API_KEY") and os.environ.get("OPENAI_API_KEY"):
        return "https://api.openai.com/v1"
    return DEFAULT_BASE_URL


def get_client():
    from openai import OpenAI
    key = _openai_key()
    if not key:
        raise RuntimeError("No LLM API key set (OPENROUTER_API_KEY).")
    return OpenAI(base_url=_base_url(), api_key=key, default_headers=_HEADERS)


def _extract_json(text: str) -> dict:
    if not text:
        return {}
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except ValueError:
            pass
    return {}


# ---------------------------------------------------------------------------
# Claude (Anthropic) plumbing
# ---------------------------------------------------------------------------

_anthropic_client = None


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    return _anthropic_client


def _to_anthropic_content(user_content):
    """Convert the OpenAI-style content the callers build (string, or a list of
    {type:text} / {type:image_url, image_url:{url:'data:...'}}) into Anthropic
    content blocks, so vision.py / complaint.py need no changes."""
    if isinstance(user_content, str):
        return user_content
    blocks = []
    for b in user_content:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            blocks.append({"type": "text", "text": b.get("text", "")})
        elif b.get("type") == "image_url":
            url = (b.get("image_url") or {}).get("url", "")
            if url.startswith("data:"):
                header, _, data = url.partition(",")
                media_type = header[5:].split(";")[0] or "image/jpeg"
                blocks.append({"type": "image", "source": {
                    "type": "base64", "media_type": media_type, "data": data}})
            elif url:
                blocks.append({"type": "image",
                               "source": {"type": "url", "url": url}})
    return blocks


def _call_anthropic(system, user_content, tool, tool_name, model, max_tokens) -> dict:
    client = _get_anthropic()
    resp = client.messages.create(
        model=_anthropic_model(model),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": _to_anthropic_content(user_content)}],
        tools=[{
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
        }],
        tool_choice={"type": "tool", "name": tool_name},
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input or {})
    # Fallback: try to salvage JSON from any text block.
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            parsed = _extract_json(getattr(block, "text", "") or "")
            if parsed:
                return parsed
    return {}


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def call_tool(system: str, user_content, tool: dict, tool_name: str,
              model: Optional[str] = None, max_tokens: int = 1500) -> dict:
    """Return structured JSON from the model. Prefers Claude (native tool use +
    vision) when ANTHROPIC_API_KEY is set; otherwise uses OpenRouter with a
    tool-call → JSON-mode fallback chain."""
    # --- Claude path ---
    if _anthropic_key():
        try:
            out = _call_anthropic(system, user_content, tool, tool_name,
                                  model, max_tokens)
            if out:
                return out
        except Exception:
            pass  # fall through to OpenRouter if a key for it also exists
        if not _openai_key():
            return {}

    # --- OpenRouter / OpenAI path ---
    client = get_client()
    mdl = model or DEFAULT_MODEL
    if mdl.startswith("claude"):          # a Claude id can't run on OpenRouter here
        mdl = os.environ.get("LEXLOCATOR_MODEL", "openai/gpt-4o-mini")
        if mdl.startswith("claude"):
            mdl = "openai/gpt-4o-mini"

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
        pass

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
