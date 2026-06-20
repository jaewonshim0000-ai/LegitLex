"""FastAPI server for LexLocator.

Endpoints:
  GET  /                          static frontend
  GET  /api/health                health + DB stats
  POST /api/ask                   structured legal verdict for a question + location
  POST /api/scan-sign             OCR a sign photo and cross-reference with code
  POST /api/geocode               reverse-geocode GPS coords
  GET  /api/jurisdiction          what data we have for a given lat/lng
  GET  /api/snapshot/{id}         download a compliance snapshot HTML
"""
from __future__ import annotations
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import config  # noqa: F401  (loads .env into os.environ on import)

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .schemas import (
    AskRequest, AskResponse, Location, SignScanResponse,
    JurisdictionResponse, Citation, ComplaintResponse, CompareRequest,
)
from . import complaint as complaint_module
from .core import (
    retrieve, hits_to_retrieved, generate_verdict, get_collection, has_api_key,
    KR_COLLECTION, KR_MODEL,
)
from . import llm
from .geo import reverse_geocode
from .vision import scan_sign as scan_sign_impl
from .snapshot import create_snapshot, snapshot_path


STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="LexLocator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache(request, call_next):
    """The frontend ships .jsx/.js that browsers cache hard — so code updates
    never reach the user. Disable caching so every load gets the latest build."""
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

# Changes on every server start, so browsers are forced to re-fetch JS/CSS
# (defeats stale browser cache without needing a manual hard refresh).
BUILD_ID = str(int(time.time()))


@app.get("/", response_class=HTMLResponse)
async def root():
    index = STATIC_DIR / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>LexLocator</h1><p>Frontend missing.</p>")
    html = index.read_text(encoding="utf-8")
    # append a cache-busting version to every local static asset URL
    html = re.sub(r'(/static/[^"\']+\.(?:jsx|js|css))\b', r'\1?v=' + BUILD_ID, html)
    return HTMLResponse(html)


# PWA: manifest + service worker must be served from the root scope so the
# installed app controls the whole origin (not just /static).
@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(STATIC_DIR / "manifest.webmanifest",
                        media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker():
    return FileResponse(
        STATIC_DIR / "sw.js", media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


# Mount remaining static files (CSS/JS)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    key = has_api_key()
    info = {
        "llm_key": key,
        "anthropic_key": key,  # kept for backward compatibility
        "provider": llm.provider_name(),
        "model": llm.DEFAULT_MODEL,
    }
    try:
        col = get_collection()
        info.update({"ok": True, "chunks": col.count()})
    except Exception as e:
        info.update({"ok": False, "error": str(e)})
    return info


# ---------------------------------------------------------------------------
# Geocode
# ---------------------------------------------------------------------------

@app.post("/api/geocode")
async def geocode(lat: float = Form(...), lng: float = Form(...)):
    loc = reverse_geocode(lat, lng)
    return loc.model_dump()


# ---------------------------------------------------------------------------
# Jurisdiction coverage report
# ---------------------------------------------------------------------------

@app.get("/api/jurisdiction", response_model=JurisdictionResponse)
async def jurisdiction(lat: float, lng: float):
    loc = reverse_geocode(lat, lng)
    col = get_collection()

    counts: dict[str, int] = {}
    covered: list[str] = []
    for lvl, key, val in [
        ("city", "city", loc.city),
        ("county", "county", loc.county),
        ("state", "state", loc.state),
    ]:
        if not val:
            continue
        try:
            res = col.get(where={key: val}, limit=1)
            sample = col.get(where={key: val}, limit=10000)
            n = len(sample.get("ids", []))
            if n > 0:
                counts[lvl] = n
                covered.append(lvl)
        except Exception:
            pass

    return JurisdictionResponse(
        location=loc,
        covered_levels=covered,
        section_count_by_level=counts,
    )


# ---------------------------------------------------------------------------
# Coverage report (real per-source breakdown for a location)
# ---------------------------------------------------------------------------

@app.get("/api/coverage")
async def coverage(lat: Optional[float] = None, lng: Optional[float] = None,
                   city: str = "", county: str = "", state: str = ""):
    if not city and lat is not None and lng is not None:
        loc = reverse_geocode(lat, lng)
    else:
        loc = Location(city=city, county=county, state=state, lat=lat, lng=lng)

    col = get_collection()
    clauses = []
    if loc.city:
        clauses.append({"city": loc.city})
    if loc.county:
        clauses.append({"county": loc.county})
    if loc.state:
        clauses.append({"state": loc.state})
    clauses.append({"level": "federal"})
    where = clauses[0] if len(clauses) == 1 else {"$or": clauses}

    # Page through results — a single huge .get() blows ChromaDB's SQL var limit.
    metas = []
    try:
        PAGE, off = 5000, 0
        while True:
            got = col.get(where=where, include=["metadatas"], limit=PAGE, offset=off)
            batch = got.get("metadatas", []) or []
            metas.extend(batch)
            if len(batch) < PAGE:
                break
            off += PAGE
            if off > 400000:
                break
    except Exception as e:
        return {"location": loc.model_dump(), "error": str(e), "sources": []}

    # aggregate unique section_ids per (level, source_title)
    agg: dict = {}
    level_ids: dict = {}
    for m in metas:
        lvl = m.get("level", "")
        src = m.get("source_title") or m.get("source_file") or "(unknown source)"
        sid = m.get("section_id", "")
        where_str = ", ".join(filter(None, [m.get("city"), m.get("county"), m.get("state")]))
        key = (lvl, src)
        a = agg.setdefault(key, {"level": lvl, "source_title": src,
                                 "jurisdiction": where_str, "ids": set()})
        a["ids"].add(sid)
        level_ids.setdefault(lvl, set()).add((src, sid))

    order = {"city": 0, "county": 1, "state": 2, "federal": 3, "": 4}
    sources = sorted(
        [{"level": a["level"], "source_title": a["source_title"],
          "jurisdiction": a["jurisdiction"], "sections": len(a["ids"])}
         for a in agg.values()],
        key=lambda s: (order.get(s["level"], 9), -s["sections"]),
    )

    counts_by_level = {lvl: len(v) for lvl, v in level_ids.items()}
    present = set(counts_by_level)
    # which applicable levels are missing for this location?
    applicable = [("city", loc.city), ("county", loc.county), ("state", loc.state)]
    missing = [lvl for lvl, val in applicable if val and lvl not in present]

    return {
        "location": loc.model_dump(),
        "sources": sources,
        "total_sections": sum(s["sections"] for s in sources),
        "counts_by_level": counts_by_level,
        "missing_levels": missing,
    }


# ---------------------------------------------------------------------------
# Ask
# ---------------------------------------------------------------------------

@app.post("/api/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    if not has_api_key():
        raise HTTPException(
            status_code=400,
            detail="No LLM API key set on the server. Add OPENROUTER_API_KEY to .env.",
        )

    location = req.location
    if (not location.city and location.lat is not None
            and location.lng is not None):
        location = reverse_geocode(location.lat, location.lng)

    hits = retrieve(req.question, location, k=8)

    # Secondary pass: penalty/fine provisions often live in a separate "general
    # penalty" section, so pull a few and merge (deduped) so the model can state
    # the actual punishment instead of "not specified".
    penalty_terms = ("벌칙 과태료 벌금 처벌 위반"
                     if (location.country or "US").strip().upper() == "KR"
                     else "penalty fine punishment violation infraction")
    penalty_hits = retrieve(f"{req.question} {penalty_terms}", location, k=4)
    seen = {(h["meta"].get("section_id"), h["meta"].get("chunk_index")) for h in hits}
    for h in penalty_hits:
        key = (h["meta"].get("section_id"), h["meta"].get("chunk_index"))
        if key not in seen:
            hits.append(h)
            seen.add(key)

    retrieved = hits_to_retrieved(hits)
    verdict = generate_verdict(
        req.question, location, hits,
        speed_kmh=req.speed_kmh, activity=req.activity,
    )
    snap_id, _ = create_snapshot(req.question, location, verdict, retrieved)

    return AskResponse(
        verdict=verdict,
        location=location,
        retrieved=retrieved,
        snapshot_id=snap_id,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Compare two locations
# ---------------------------------------------------------------------------

@app.post("/api/compare")
async def compare(req: CompareRequest):
    if not has_api_key():
        raise HTTPException(status_code=400,
                            detail="No LLM API key set on the server. Add OPENROUTER_API_KEY to .env.")

    results = []
    for loc in (req.location_a, req.location_b):
        location = loc
        if not location.city and location.lat is not None and location.lng is not None:
            location = reverse_geocode(location.lat, location.lng)
        hits = retrieve(req.question, location, k=8)
        verdict = generate_verdict(req.question, location, hits)
        results.append({
            "location": location.model_dump(),
            "verdict": verdict.model_dump(),
            "citation_count": len(verdict.citations),
        })

    return {
        "question": req.question,
        "results": results,
        "differ": results[0]["verdict"]["verdict"] != results[1]["verdict"]["verdict"],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Scan sign (multipart upload)
# ---------------------------------------------------------------------------

@app.post("/api/scan-sign", response_model=SignScanResponse)
async def scan_sign(
    image: UploadFile = File(...),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    city: str = Form(""),
    state: str = Form(""),
):
    if not has_api_key():
        raise HTTPException(
            status_code=400,
            detail="No LLM API key set on the server. Add OPENROUTER_API_KEY to .env.",
        )

    if lat is not None and lng is not None and not city:
        location = reverse_geocode(lat, lng)
    else:
        location = Location(city=city, state=state, lat=lat, lng=lng)

    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image upload.")

    result = scan_sign_impl(data, location)
    return SignScanResponse(
        sign_text=result["sign_text"],
        extracted_rule=result["extracted_rule"],
        verified_against_code=result["verified_against_code"],
        matching_citations=result["matching_citations"],
        note=("Sign appears official." if result["appears_official"]
              else "Sign may be unofficial, private, or handmade."),
        location=location,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Analyze complaint (multipart: file upload and/or pasted text)
# ---------------------------------------------------------------------------

@app.post("/api/analyze-complaint", response_model=ComplaintResponse)
async def analyze_complaint(
    file: Optional[UploadFile] = File(None),
    text: str = Form(""),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    city: str = Form(""),
    county: str = Form(""),
    state: str = Form(""),
):
    if not has_api_key():
        raise HTTPException(
            status_code=400,
            detail="No LLM API key set on the server. Add OPENROUTER_API_KEY to .env.",
        )

    if lat is not None and lng is not None and not city:
        location = reverse_geocode(lat, lng)
    else:
        location = Location(city=city, county=county, state=state, lat=lat, lng=lng)

    complaint_text = (text or "").strip()
    if file is not None:
        data = await file.read()
        if data:
            complaint_text = complaint_module.extract_text(
                data, file.filename or "", file.content_type or "")
    if not complaint_text:
        raise HTTPException(
            status_code=400,
            detail="No complaint text found. Upload a PDF/text/image or paste the text.",
        )

    analysis, hits = complaint_module.analyze(complaint_text, location)
    retrieved = hits_to_retrieved(hits)
    snap_id = uuid.uuid4().hex[:12]

    return ComplaintResponse(
        analysis=analysis,
        location=location,
        extracted_text_preview=complaint_text[:600],
        retrieved=retrieved,
        snapshot_id=snap_id,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Snapshot download
# ---------------------------------------------------------------------------

@app.get("/api/snapshot/{snap_id}")
async def snapshot(snap_id: str):
    p = snapshot_path(snap_id)
    if not p:
        raise HTTPException(status_code=404, detail="Snapshot not found.")
    return FileResponse(p, media_type="text/html", filename=f"lexlocator_{snap_id}.html")


# ---------------------------------------------------------------------------
# Warm up both collections + their embedding models NOW, in the main thread, at
# import time (before uvicorn starts its event loop). If laws_kr is first loaded
# lazily inside the async event loop, ChromaDB silently falls back to the default
# English model and caches it — so Korean retrieval returns garbage. Building it
# here, eagerly, guarantees the multilingual model is bound and cached correctly.
# ---------------------------------------------------------------------------

def _warmup():
    try:
        get_collection()                                       # US / English model
    except Exception as e:
        print(f"[warmup] laws: {e}")
    try:
        get_collection(name=KR_COLLECTION, model_name=KR_MODEL)  # Korea / multilingual
    except Exception as e:
        print(f"[warmup] laws_kr: {e}")


_warmup()


# ---------------------------------------------------------------------------
# Entry point: python -m lexlocator.server
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("lexlocator.server:app", host="127.0.0.1", port=port, reload=False)
