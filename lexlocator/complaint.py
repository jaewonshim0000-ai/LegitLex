"""
Complaint analysis: take a scanned/uploaded complaint, notice, or citation and
produce a plain-English summary + risk assessment grounded in the laws in this
app's dataset.

Pipeline:
  1. Get the complaint text:
       - PDF  -> pdfplumber (no vision model needed)
       - image -> Claude/LLM vision OCR (needs a vision-capable model)
       - text -> used as-is
  2. RAG-retrieve the most relevant law sections for the user's location.
  3. Force a structured ComplaintAnalysis via the LLM, citing ONLY retrieved law.
"""
from __future__ import annotations
import base64
import io
from typing import Optional

from .schemas import Location, Citation, ComplaintAnalysis, Allegation
from . import core, llm


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _is_pdf(data: bytes, name: str, ctype: str) -> bool:
    return data[:5] == b"%PDF-" or name.lower().endswith(".pdf") or ctype == "application/pdf"


def _is_image(data: bytes, ctype: str) -> bool:
    return (ctype or "").startswith("image/") or data[:3] == b"\xff\xd8\xff" \
        or data[:8] == b"\x89PNG\r\n\x1a\n"


def extract_text(data: bytes, filename: str = "", content_type: str = "",
                 max_pages: int = 25) -> str:
    """Return the complaint text from an uploaded PDF, image, or text blob."""
    if not data:
        return ""
    if _is_pdf(data, filename, content_type):
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                pages = pdf.pages[:max_pages]
                return "\n".join((p.extract_text() or "") for p in pages).strip()
        except Exception:
            return ""
    if _is_image(data, content_type):
        return _ocr_image(data, content_type)
    # plain text
    return data.decode("utf-8", "ignore").strip()


def _ocr_image(data: bytes, content_type: str) -> str:
    """Transcribe an image of a complaint using the LLM's vision capability.
    Returns '' if the configured model has no vision support."""
    media = content_type if content_type.startswith("image/") else "image/jpeg"
    b64 = base64.standard_b64encode(data).decode("ascii")
    tool = {
        "name": "report_text",
        "description": "Return all readable text transcribed from the document image.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    }
    out = llm.call_tool(
        system="You transcribe documents. Return all readable text verbatim.",
        user_content=[
            {"type": "text", "text": "Transcribe every word of this complaint/notice."},
            {"type": "image_url", "image_url": {"url": f"data:{media};base64,{b64}"}},
        ],
        tool=tool, tool_name="report_text", max_tokens=2000,
    )
    return (out or {}).get("text", "")


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

COMPLAINT_TOOL = {
    "name": "analyze_complaint",
    "description": (
        "Summarize a legal complaint/notice/citation in plain English and assess "
        "the recipient's risk, citing ONLY the retrieved law sections. Never "
        "invent statutes, penalties, or deadlines not present in the inputs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {"type": "string",
                        "description": "Plain-English summary, 2-4 sentences."},
            "complaint_type": {"type": "string"},
            "allegations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "law_area": {"type": "string"},
                    },
                    "required": ["claim"],
                },
            },
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "level": {"type": "string",
                                  "enum": ["city", "county", "state", "federal", "unknown"]},
                        "jurisdiction": {"type": "string"},
                        "section_id": {"type": "string"},
                        "section_name": {"type": "string"},
                        "paraphrase": {"type": "string"},
                        "source_url": {"type": "string"},
                        "page_start": {"type": "integer"},
                    },
                    "required": ["section_id", "paraphrase"],
                },
            },
            "risk_level": {"type": "string",
                           "enum": ["low", "medium", "high", "critical", "unknown"]},
            "risk_rationale": {"type": "string"},
            "potential_penalties": {"type": "string"},
            "recommended_actions": {"type": "array", "items": {"type": "string"}},
            "deadline": {"type": "string"},
            "caveats": {"type": "string"},
        },
        "required": ["summary", "complaint_type", "allegations", "citations",
                     "risk_level", "risk_rationale", "potential_penalties",
                     "recommended_actions", "deadline", "caveats"],
    },
}

SYSTEM_PROMPT = """You are LexLocator's complaint analyst. You receive the text
of a legal complaint, code-enforcement notice, citation, or similar document,
the recipient's location, and law sections retrieved from official city/county/
state/federal codes for that location.

Call analyze_complaint with:
- A clear plain-English summary a non-lawyer understands.
- The specific allegations (what the person is accused of).
- citations: ONLY law sections from the retrieved set that actually apply. If
  none of the retrieved law is on point, leave citations empty and say so.
- risk_level: low / medium / high / critical, based on the seriousness of the
  allegations and the penalties in the retrieved law (criminal/large fines =
  higher). Use 'unknown' if you truly can't tell.
- potential_penalties: ONLY from the retrieved law; never invent amounts.
- recommended_actions: practical, general steps (meet any deadline, gather
  evidence, contact the issuing office, consult an attorney). These are general
  information, NOT legal advice.
- deadline: copy any response deadline stated in the document; else ''.
Be calm, factual, and non-alarmist. Never fabricate statutes, penalties, or
deadlines.
"""


def _format_context(text: str, location: Location, hits: list[dict]) -> str:
    where = ", ".join(filter(None, [location.city, location.county, location.state]))
    laws = core._format_context(hits) if hits else "(no matching law retrieved)"
    return (
        f"Recipient location: {where or 'unknown'}\n\n"
        f"COMPLAINT TEXT:\n\"\"\"\n{text[:12000]}\n\"\"\"\n\n"
        f"RETRIEVED LAW SECTIONS:\n\n{laws}"
    )


def _coerce(payload: dict) -> ComplaintAnalysis:
    risk = str(payload.get("risk_level") or "unknown").lower().strip()
    if risk not in ("low", "medium", "high", "critical", "unknown"):
        risk = "unknown"
    citations = []
    for c in (payload.get("citations") or []):
        if isinstance(c, dict):
            citations.append(core._coerce_citation(c))
    allegations = []
    for a in (payload.get("allegations") or []):
        if isinstance(a, dict) and a.get("claim"):
            allegations.append(Allegation(claim=str(a["claim"]),
                                          law_area=str(a.get("law_area") or "")))
    actions = [str(x) for x in (payload.get("recommended_actions") or []) if x]
    return ComplaintAnalysis(
        summary=str(payload.get("summary") or ""),
        complaint_type=str(payload.get("complaint_type") or ""),
        allegations=allegations,
        citations=citations,
        risk_level=risk,
        risk_rationale=str(payload.get("risk_rationale") or ""),
        potential_penalties=str(payload.get("potential_penalties") or ""),
        recommended_actions=actions,
        deadline=str(payload.get("deadline") or ""),
        caveats=str(payload.get("caveats") or ""),
    )


def analyze(text: str, location: Location,
            model: Optional[str] = None) -> tuple[ComplaintAnalysis, list[dict]]:
    """Return (ComplaintAnalysis, retrieved_hits)."""
    text = (text or "").strip()
    if len(text) < 25:
        empty = ComplaintAnalysis(
            summary="No readable text was found in the upload.",
            risk_level="unknown",
            caveats="Could not extract text. For images, use a vision-capable "
                    "model, or paste the complaint text directly.",
        )
        return empty, []

    # Retrieve law for the complaint topics (+ a penalty-focused pass).
    hits = core.retrieve(text, location, k=10)
    pen = core.retrieve(text + " penalty fine punishment violation", location, k=4)
    seen = {(h["meta"].get("section_id"), h["meta"].get("chunk_index")) for h in hits}
    for h in pen:
        key = (h["meta"].get("section_id"), h["meta"].get("chunk_index"))
        if key not in seen:
            hits.append(h); seen.add(key)

    payload = llm.call_tool(
        system=SYSTEM_PROMPT,
        user_content=_format_context(text, location, hits),
        tool=COMPLAINT_TOOL, tool_name="analyze_complaint",
        model=model, max_tokens=2500,
    )
    if not payload:
        return ComplaintAnalysis(
            summary="The model could not analyze this complaint. Try again or "
                    "paste the text directly.",
            risk_level="unknown",
        ), hits
    return _coerce(payload), hits
