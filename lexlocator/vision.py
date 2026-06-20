"""Sign scanning via Claude vision.

Pipeline:
  1. User uploads photo of a posted sign.
  2. Claude reads the image, extracts visible text and the rule it expresses.
  3. We RAG-search the extracted rule against the official code for the user's
     location. If a matching ordinance exists, the sign is considered
     "verified against code." If not, it may be private/outdated/unofficial.
"""
from __future__ import annotations
import base64
import io
from typing import Optional

from .schemas import Location, Citation, SignScanResponse
from .core import retrieve, hits_to_retrieved
from . import llm


SIGN_READER_TOOL = {
    "name": "report_sign",
    "description": "Report what is on the sign visible in the image.",
    "parameters": {
        "type": "object",
        "properties": {
            "sign_text": {
                "type": "string",
                "description": "All readable text on the sign, transcribed verbatim.",
            },
            "extracted_rule": {
                "type": "string",
                "description": (
                    "Plain-English statement of the rule the sign communicates. "
                    "E.g. 'No parking between 2am and 6am' or 'E-bikes prohibited "
                    "on this path.' Empty string if no rule is communicated."
                ),
            },
            "appears_official": {
                "type": "boolean",
                "description": (
                    "True if the sign LOOKS like an official municipal sign "
                    "(standardized format, agency mark, regulatory symbols). "
                    "False if it looks handwritten, private, or improvised."
                ),
            },
            "search_keywords": {
                "type": "string",
                "description": (
                    "A short search phrase to cross-reference against municipal "
                    "code. E.g. 'parking overnight curfew' or 'e-bike trail "
                    "prohibition'."
                ),
            },
        },
        "required": ["sign_text", "extracted_rule", "appears_official",
                     "search_keywords"],
    },
}


SIGN_SYSTEM = """You are reading a photograph of a posted sign for a user who
wants to know if its rule is legally enforceable in their location.

Call `report_sign` with what you see. Be literal: transcribe text exactly,
and only summarize the rule the sign actually states. If the sign has no
rule (a name, a logo, a direction arrow), say so by setting extracted_rule
to empty.
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
    return "image/jpeg"  # best guess


def _maybe_resize(image_bytes: bytes, max_dim: int = 1600) -> bytes:
    """Downsize huge phone photos so the API call stays cheap and fast."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        if max(w, h) <= max_dim:
            return image_bytes
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)))
        out = io.BytesIO()
        fmt = "JPEG" if img.mode == "RGB" else "PNG"
        if fmt == "JPEG" and img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out, format=fmt, quality=85)
        return out.getvalue()
    except Exception:
        return image_bytes


def scan_sign(image_bytes: bytes, location: Location,
              model: str = None) -> dict:
    """
    Returns dict with:
      sign_text, extracted_rule, appears_official, search_keywords,
      matching_citations, verified_against_code
    """
    image_bytes = _maybe_resize(image_bytes)
    media_type = _detect_media_type(image_bytes)
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    data_url = f"data:{media_type};base64,{b64}"

    # OpenAI-compatible vision content blocks (works on OpenRouter).
    sign_data = llm.call_tool(
        system=SIGN_SYSTEM,
        user_content=[
            {"type": "text", "text": "Read this sign and report its rule."},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
        tool=SIGN_READER_TOOL,
        tool_name="report_sign",
        model=model,
        max_tokens=1000,
    )

    # Cross-reference: RAG-search the extracted rule
    matching_citations: list[Citation] = []
    verified = False
    search = sign_data.get("search_keywords") or sign_data.get("extracted_rule", "")
    if search and location.state:
        hits = retrieve(search, location, k=5)
        # Only consider strong matches (low cosine distance)
        strong = [h for h in hits if h["distance"] < 0.7]
        for h in strong[:3]:
            m = h["meta"]
            where = ", ".join(filter(None, [m.get("city"), m.get("county"), m.get("state")]))
            matching_citations.append(Citation(
                level=m.get("level", "unknown"),
                jurisdiction=where,
                section_id=m.get("section_id", ""),
                section_name=m.get("section_name", ""),
                paraphrase=h["text"][:200],
                source_url=m.get("source_url", ""),
                page_start=int(m.get("page_start", 0) or 0),
            ))
        verified = len(strong) > 0

    return {
        "sign_text": sign_data.get("sign_text", ""),
        "extracted_rule": sign_data.get("extracted_rule", ""),
        "appears_official": sign_data.get("appears_official", False),
        "search_keywords": sign_data.get("search_keywords", ""),
        "matching_citations": matching_citations,
        "verified_against_code": verified,
    }
