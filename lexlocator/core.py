"""Core RAG: retrieval from ChromaDB + structured Verdict from Claude.

Claude is required to produce a Verdict by calling the `provide_verdict` tool;
this is how we guarantee citation-bearing JSON output and prevent hallucinated
free-form answers.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from .schemas import (
    Location, Verdict, Citation, RetrievedSection,
)
from . import llm

# Model used for verdicts/sign-reading. Override with LEXLOCATOR_MODEL in .env.
DEFAULT_MODEL = llm.DEFAULT_MODEL


# ---------------------------------------------------------------------------
# ChromaDB
# ---------------------------------------------------------------------------

# US/English content is embedded with a fast English model. Korean statutes live
# in a SEPARATE collection embedded with a multilingual model, because the
# English model can't meaningfully embed Korean (retrieval would be near-random).
EN_MODEL = "all-MiniLM-L6-v2"
KR_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
KR_COLLECTION = "laws_kr"

_client = None
_collections: dict[str, object] = {}
_embed_fns: dict[str, object] = {}


def _get_client(db_path: str | Path = "vectordb"):
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection(db_path: str | Path = "vectordb", name: str = "laws",
                   model_name: str = EN_MODEL):
    """Return (and cache) a collection bound to its embedding model. The US
    `laws` collection uses the English model; `laws_kr` uses the multilingual one."""
    if name not in _collections:
        if model_name not in _embed_fns:
            _embed_fns[model_name] = (
                embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=model_name
                )
            )
        _collections[name] = _get_client(db_path).get_collection(
            name=name, embedding_function=_embed_fns[model_name]
        )
    return _collections[name]


def _build_filter(loc: Location) -> Optional[dict]:
    """ChromaDB metadata filter, scoped to the user's country.

    KR: Korean national statutes only (country-tagged), so US law never appears
    for a Seoul user. US (default): the user's city/county/state layers plus the
    federal floor. Korean rows carry level='national' with empty city/county/
    state, so they can't match the US clauses and never leak into US queries —
    which is why the US path needs no explicit country constraint (that would
    also risk excluding any older chunks ingested before the country field).
    """
    country = (loc.country or "US").strip().upper()
    if country == "KR":
        return {"country": "KR"}

    clauses = []
    if loc.city:
        clauses.append({"city": loc.city})
    if loc.county:
        clauses.append({"county": loc.county})
    if loc.state:
        clauses.append({"state": loc.state})
    clauses.append({"level": "federal"})
    if len(clauses) == 1:
        return clauses[0]
    return {"$or": clauses}


def retrieve(question: str, location: Location, k: int = 8) -> list[dict]:
    """Returns list of {text, meta, distance}.

    Korean users hit the multilingual `laws_kr` collection; everyone else hits
    the English `laws` collection. The two never mix, so US law can't surface
    for a Seoul user and vice versa."""
    if (location.country or "US").strip().upper() == "KR":
        col = get_collection(name=KR_COLLECTION, model_name=KR_MODEL)
        where = None   # laws_kr holds only KR statutes; no further filter needed
    else:
        col = get_collection()
        where = _build_filter(location)
    res = col.query(
        query_texts=[question],
        n_results=k,
        where=where,
    )
    hits = []
    if not res.get("documents") or not res["documents"][0]:
        return hits
    for i, doc in enumerate(res["documents"][0]):
        hits.append({
            "text": doc,
            "meta": res["metadatas"][0][i],
            "distance": float(res["distances"][0][i]) if res.get("distances") else 1.0,
        })
    return hits


def hits_to_retrieved(hits: list[dict]) -> list[RetrievedSection]:
    out = []
    for h in hits:
        m = h["meta"]
        where = ", ".join(filter(None, [m.get("city"), m.get("county"), m.get("state")]))
        out.append(RetrievedSection(
            section_id=m.get("section_id", "?"),
            section_name=m.get("section_name", ""),
            level=m.get("level", "unknown"),
            jurisdiction=where,
            breadcrumb=m.get("breadcrumb", ""),
            page_start=int(m.get("page_start", 0) or 0),
            distance=h["distance"],
            text_preview=h["text"][:300],
        ))
    return out


# ---------------------------------------------------------------------------
# Tool/function schema: forces a structured Verdict response
# ---------------------------------------------------------------------------

VERDICT_TOOL = {
    "name": "provide_verdict",
    "description": (
        "Provide a structured legal verdict on the user's question, citing "
        "only the law sections that were retrieved. Use verdict='unknown' "
        "and empty citations if the retrieved sections do not actually "
        "answer the question. Never invent section numbers."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["yes", "no", "warning", "unknown"],
                "description": (
                    "'yes' = activity is clearly allowed by retrieved law. "
                    "'no' = clearly prohibited. "
                    "'warning' = conditionally allowed with restrictions. "
                    "'unknown' = retrieved law does not answer the question."
                ),
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "How confident the retrieved sections settle this. 0.0-1.0.",
            },
            "answer": {
                "type": "string",
                "description": "Plain-English answer, 1-3 sentences.",
            },
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "level": {
                            "type": "string",
                            "enum": ["city", "county", "state", "federal", "unknown"],
                        },
                        "jurisdiction": {"type": "string"},
                        "section_id": {"type": "string"},
                        "section_name": {"type": "string"},
                        "paraphrase": {"type": "string"},
                        "source_url": {"type": "string"},
                        "page_start": {"type": "integer"},
                        "last_amended": {
                            "type": "string",
                            "description": "The 4-digit YEAR this section was most "
                            "recently amended/added, taken from its history note "
                            "(e.g. 'Amended by Stats. 2024' -> '2024'). '' if unknown.",
                        },
                    },
                    "required": ["section_id", "paraphrase"],
                },
            },
            "caveats": {
                "type": "string",
                "description": "What's NOT covered (e.g. state/federal not retrieved).",
            },
            "penalty": {
                "type": "string",
                "description": (
                    "The fine or punishment for doing this, taken ONLY from the "
                    "retrieved law text. Plain English, e.g. 'Infraction: fine up "
                    "to $250 for a first offense.' If the retrieved sections do "
                    "not state a penalty, set this to 'Not specified in the "
                    "retrieved law.' Never invent a dollar amount."
                ),
            },
            "penalty_severity": {
                "type": "string",
                "enum": ["none", "infraction", "civil", "misdemeanor", "felony", "unknown"],
                "description": (
                    "Severity tier for UI coloring. 'none' if the action is "
                    "allowed (verdict=yes). 'unknown' if the retrieved law does "
                    "not state a penalty."
                ),
            },
            "conflicts": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "List any place the jurisdiction layers DISAGREE in the "
                    "retrieved law (city vs county vs state vs federal). Each entry "
                    "names the two levels, what each says, and which one governs "
                    "here (usually the stricter / more local rule, but federal "
                    "floors apply everywhere). Empty list if the layers agree or "
                    "only one level applies."
                ),
            },
        },
        "required": ["verdict", "confidence", "answer", "citations", "caveats",
                     "penalty", "penalty_severity", "conflicts"],
    },
}


SYSTEM_PROMPT = """You are LexLocator, a hyper-local legal compliance assistant.

You receive: the user's question, their GPS-derived location, optional real-time
context (speed, activity), and a set of law sections retrieved from official
city / county / state / federal codes for their location.

Your job: call the `provide_verdict` tool with a strictly grounded answer.

RULES:
1. Only cite section_ids that appear in the retrieved sections. Never invent.
2. If the retrieved sections do not actually answer the question, set
   verdict='unknown', confidence=0, citations=[], and say so in `answer`.
3. Prefer specific over general: a section about "Class 3 e-bikes on bike paths"
   beats a section about "all vehicles."
4. If multiple jurisdictions apply, mention each (city overrides county overrides
   state where applicable, but federal floors apply everywhere).
5. In `caveats`, name the jurisdiction levels that were NOT in the retrieved set
   but might be relevant.
6. The user is making a real-time on-the-ground decision. Be direct.
8. CONFLICTS: you have law from multiple levels (city/county/state/federal).
   If they disagree on this question, list each disagreement in `conflicts` and
   say which level governs (more-local/stricter usually wins; federal floors
   apply everywhere). If they agree or only one level applies, use an empty list.
7. PENALTY: scan the retrieved sections for any stated fine, fee, or punishment
   (e.g. "infraction", "misdemeanor", "fine not exceeding $___", "punishable by").
   Put it in `penalty` verbatim-grounded and set `penalty_severity` accordingly.
   If no penalty appears in the retrieved text, set penalty='Not specified in the
   retrieved law.' and penalty_severity='unknown'. If verdict='yes' (allowed),
   set penalty='None — this is allowed.' and penalty_severity='none'. NEVER
   invent a dollar amount or charge level that isn't in the retrieved law.
"""


def _format_context(hits: list[dict]) -> str:
    blocks = []
    for h in hits:
        m = h["meta"]
        where = ", ".join(filter(None, [m.get("city"), m.get("county"), m.get("state")]))
        header = f"[{m.get('level', '?')}: {where}] § {m.get('section_id', '?')}"
        if m.get("section_name"):
            header += f" -- {m['section_name']}"
        if m.get("breadcrumb"):
            header += f"\nPath: {m['breadcrumb']}"
        if m.get("source_title"):
            header += f"\nSource: {m['source_title']}"
        blocks.append(f"{header}\n\n{h['text']}")
    return "\n\n---\n\n".join(blocks)


def _format_user_message(question: str, location: Location, hits: list[dict],
                        speed_kmh: Optional[float] = None,
                        activity: Optional[str] = None) -> str:
    where = ", ".join(filter(None, [location.city, location.county, location.state]))
    ctx_lines = [f"User location: {where or 'unknown'}"]
    if location.lat is not None and location.lng is not None:
        ctx_lines.append(f"GPS: ({location.lat:.4f}, {location.lng:.4f})")
    if speed_kmh is not None:
        ctx_lines.append(f"Current speed: {speed_kmh:.1f} km/h")
    if activity:
        ctx_lines.append(f"Activity context: {activity}")

    return (
        "\n".join(ctx_lines)
        + f"\n\nUser question: {question}\n\n"
        + "Retrieved law sections:\n\n"
        + (_format_context(hits) if hits else "(no matching sections found)")
    )


def generate_verdict(question: str, location: Location, hits: list[dict],
                     speed_kmh: Optional[float] = None,
                     activity: Optional[str] = None,
                     model: Optional[str] = None) -> Verdict:
    """Send retrieved hits to the LLM, force a structured tool call, parse it."""
    if not hits:
        return Verdict(
            verdict="unknown",
            confidence=0.0,
            answer=("No matching ordinances were found in the local database for "
                    "your location. The relevant city/county/state code may not "
                    "be ingested yet."),
            citations=[],
            caveats="No law sections were retrieved.",
        )

    payload = llm.call_tool(
        system=SYSTEM_PROMPT,
        user_content=_format_user_message(question, location, hits,
                                          speed_kmh, activity),
        tool=VERDICT_TOOL,
        tool_name="provide_verdict",
        model=model,
        max_tokens=2000,
    )

    if not payload:
        return Verdict(
            verdict="unknown", confidence=0.0,
            answer="The model did not return a structured verdict. Try again.",
            citations=[], caveats="",
        )

    citations = [_coerce_citation(c) for c in (payload.get("citations") or [])
                 if isinstance(c, dict)]

    verdict = str(payload.get("verdict") or "unknown").lower().strip()
    if verdict not in ("yes", "no", "warning", "unknown"):
        verdict = "unknown"
    try:
        confidence = float(payload.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    severity = str(payload.get("penalty_severity") or "unknown").lower().strip()
    if severity not in ("none", "infraction", "civil", "misdemeanor", "felony", "unknown"):
        severity = "unknown"

    conflicts = [str(c) for c in (payload.get("conflicts") or []) if c and str(c).strip()]

    return Verdict(
        verdict=verdict,
        confidence=confidence,
        answer=str(payload.get("answer") or ""),
        citations=citations,
        caveats=str(payload.get("caveats") or ""),
        penalty=str(payload.get("penalty") or ""),
        penalty_severity=severity,
        conflicts=conflicts,
    )


_VALID_LEVELS = {"city", "county", "state", "federal", "unknown"}


def _coerce_citation(c: dict) -> Citation:
    """Build a Citation tolerant of nulls / missing / wrong-typed fields, which
    free and open models frequently emit (e.g. source_url: null)."""
    level = str(c.get("level") or "unknown").lower().strip()
    if level not in _VALID_LEVELS:
        level = "unknown"
    try:
        page = int(c.get("page_start") or 0)
    except (TypeError, ValueError):
        page = 0
    ym = re.search(r"(19|20)\d{2}", str(c.get("last_amended") or ""))
    last_amended = ym.group(0) if ym else ""
    return Citation(
        section_id=str(c.get("section_id") or "?"),
        paraphrase=str(c.get("paraphrase") or ""),
        level=level,
        jurisdiction=str(c.get("jurisdiction") or ""),
        section_name=str(c.get("section_name") or ""),
        source_url=str(c.get("source_url") or ""),
        page_start=page,
        last_amended=last_amended,
    )


def has_api_key() -> bool:
    return llm.has_api_key()
