"""Photo → relevant laws, in plain language.

Pipeline:
  1. User takes/uploads a photo of a situation (riding an e-scooter, a dog off
     leash, a parked car, a campfire on a beach, a posted sign, …).
  2. Claude vision describes the legally-relevant things in the photo and
     proposes search phrases.
  3. We RAG-search those against the official code for the user's location.
  4. Claude turns ONLY the retrieved law into a short, plain-language list of
     the laws that apply to what's in the photo — each with its citation.
"""
from __future__ import annotations
import base64
import io
from typing import Optional

from .schemas import Location, Citation
from .core import retrieve, hits_to_retrieved
from . import llm


# --- Pass 1: vision — what's in the photo? ----------------------------------

SCENE_TOOL = {
    "name": "describe_scene",
    "description": "Describe what is in the photo, focusing on anything with "
                   "legal relevance (activities, vehicles, animals, objects, "
                   "signs, the setting/place).",
    "parameters": {
        "type": "object",
        "properties": {
            "scene": {
                "type": "string",
                "description": "1-2 plain-English sentences describing what is "
                               "happening in the photo.",
            },
            "subjects": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The legally-relevant things in the photo: "
                               "activities, objects, vehicles, animals, place "
                               "type. E.g. ['riding an electric scooter', 'on a "
                               "public sidewalk', 'no helmet'].",
            },
            "queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-4 short search phrases to find laws that could "
                               "apply. E.g. ['electric scooter sidewalk', "
                               "'scooter helmet requirement'].",
            },
        },
        "required": ["scene", "subjects", "queries"],
    },
}

SCENE_SYSTEM = """You are looking at a photo for a user who wants to know which
local laws apply to what's in it. Call `describe_scene`. Be concrete about the
activity, objects, and setting — those drive which laws are relevant. If the
photo is a posted sign, transcribe its rule as part of the scene."""


# --- Pass 2: grounded plain-language laws -----------------------------------

LAWS_TOOL = {
    "name": "relevant_laws",
    "description": "List the laws most relevant to what's in the photo, using "
                   "ONLY the retrieved law sections, explained simply.",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "1-2 sentence plain-language overview of the legal "
                               "picture for this photo. If no retrieved law is "
                               "relevant, say so plainly.",
            },
            "laws": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string",
                                  "description": "Short title, e.g. 'Helmet "
                                  "required for e-scooter riders under 18'."},
                        "explanation": {"type": "string",
                                        "description": "1-2 sentences, simple "
                                        "language: what this law means for the "
                                        "situation in the photo."},
                        "level": {"type": "string",
                                  "enum": ["city", "county", "state", "federal",
                                           "national", "unknown"]},
                        "jurisdiction": {"type": "string"},
                        "section_id": {"type": "string"},
                        "section_name": {"type": "string"},
                        "source_url": {"type": "string"},
                        "page_start": {"type": "integer"},
                    },
                    "required": ["topic", "explanation", "section_id"],
                },
                "description": "The relevant laws. Empty if none of the retrieved "
                               "sections actually apply. Never invent a section.",
            },
        },
        "required": ["summary", "laws"],
    },
}

LAWS_SYSTEM = """You explain the law in plain language to an ordinary person.

You are given: a description of what's in a user's photo, their location, and a
set of law sections retrieved from official city/county/state/federal (or Korean
national) codes for that location.

Call `relevant_laws`. Rules:
1. Use ONLY the retrieved sections. Never invent a section number or a law.
2. Pick the sections that actually relate to what's in the photo. Skip the rest.
3. Write each explanation in simple, everyday language — no legalese — and tie it
   to the photo ("Because you're riding an e-scooter on the sidewalk, …").
4. If none of the retrieved sections genuinely apply, return an empty `laws`
   list and say so in `summary`.
"""


def _detect_media_type(image_bytes: bytes) -> str:
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _maybe_resize(image_bytes: bytes, max_dim: int = 1600) -> bytes:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        if max(w, h) <= max_dim:
            return image_bytes
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()
    except Exception:
        return image_bytes


def _coerce(c: dict) -> Citation:
    level = str(c.get("level") or "unknown").lower().strip()
    if level not in ("city", "county", "state", "federal", "unknown"):
        level = "unknown"   # Citation enum has no 'national'
    try:
        page = int(c.get("page_start") or 0)
    except (TypeError, ValueError):
        page = 0
    return Citation(
        section_id=str(c.get("section_id") or "?"),
        section_name=str(c.get("section_name") or c.get("topic") or ""),
        paraphrase=str(c.get("explanation") or ""),
        level=level,
        jurisdiction=str(c.get("jurisdiction") or ""),
        source_url=str(c.get("source_url") or ""),
        page_start=page,
    )


def analyze_photo(image_bytes: bytes, location: Location,
                  model: str = None) -> dict:
    """Returns: {scene, summary, laws:[{topic, explanation, citation}], retrieved}."""
    image_bytes = _maybe_resize(image_bytes)
    media_type = _detect_media_type(image_bytes)
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    data_url = f"data:{media_type};base64,{b64}"

    # Pass 1 — vision
    scene_data = llm.call_tool(
        system=SCENE_SYSTEM,
        user_content=[
            {"type": "text", "text": "What's in this photo, and what laws might apply?"},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
        tool=SCENE_TOOL,
        tool_name="describe_scene",
        model=model,
        max_tokens=700,
    )
    scene = str(scene_data.get("scene") or "").strip()
    subjects = [str(s) for s in (scene_data.get("subjects") or []) if s]
    queries = [str(q) for q in (scene_data.get("queries") or []) if q]
    if not queries:
        queries = subjects or ([scene] if scene else [])

    # Retrieve law for each query (deduped)
    hits, seen = [], set()
    for q in queries[:4]:
        for h in retrieve(q, location, k=5):
            key = (h["meta"].get("section_id"), h["meta"].get("chunk_index"))
            if key not in seen:
                seen.add(key)
                hits.append(h)
    hits = hits[:12]

    if not hits:
        return {
            "scene": scene or "We couldn't identify a clear subject in the photo.",
            "summary": ("No specific local law was found in the database for what's "
                        "in this photo. The relevant code may not be ingested yet."),
            "laws": [],
            "retrieved": [],
        }

    # Pass 2 — grounded plain-language laws
    from .core import _format_context  # reuse the same law-block formatter
    where = ", ".join(filter(None, [location.city, location.county, location.state])) or "your area"
    user_msg = (
        f"User location: {where}\n\n"
        f"What's in the photo: {scene}\n"
        f"Notable elements: {', '.join(subjects) if subjects else '(see description)'}\n\n"
        f"Retrieved law sections:\n\n{_format_context(hits)}"
    )
    out = llm.call_tool(
        system=LAWS_SYSTEM,
        user_content=user_msg,
        tool=LAWS_TOOL,
        tool_name="relevant_laws",
        model=model,
        max_tokens=1600,
    )

    laws = []
    for item in (out.get("laws") or []):
        if not isinstance(item, dict):
            continue
        laws.append({
            "topic": str(item.get("topic") or "").strip(),
            "explanation": str(item.get("explanation") or "").strip(),
            "citation": _coerce(item),
        })

    return {
        "scene": scene,
        "summary": str(out.get("summary") or "").strip(),
        "laws": laws,
        "retrieved": hits_to_retrieved(hits),
    }


# Backwards-compatible alias (older callers/imports).
scan_sign = analyze_photo
