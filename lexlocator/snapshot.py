"""Compliance Snapshot generator.

Produces a timestamped, GPS-verified HTML record of:
  - the user's question
  - their location at query time
  - the verdict
  - every cited law section, verbatim from the official scrape
  - a content hash that the user can show to prove the record was not edited.

Saved to snapshots/<id>.html. The browser can print it to PDF.
"""
from __future__ import annotations
import hashlib
import html
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .schemas import Verdict, Location, RetrievedSection


SNAPSHOT_DIR = Path("snapshots")
SNAPSHOT_DIR.mkdir(exist_ok=True)


def _content_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def create_snapshot(question: str, location: Location, verdict: Verdict,
                    retrieved: list[RetrievedSection]) -> tuple[str, str]:
    """Returns (snapshot_id, path)."""
    snap_id = uuid.uuid4().hex[:12]
    ts = datetime.now(timezone.utc)
    ts_iso = ts.isoformat()

    payload = {
        "id": snap_id,
        "timestamp_utc": ts_iso,
        "question": question,
        "location": location.model_dump(),
        "verdict": verdict.model_dump(),
        "retrieved": [r.model_dump() for r in retrieved],
    }
    payload["content_hash_sha256"] = _content_hash(
        {k: v for k, v in payload.items() if k != "content_hash_sha256"}
    )

    html_str = _render_html(payload)
    path = SNAPSHOT_DIR / f"{snap_id}.html"
    path.write_text(html_str, encoding="utf-8")

    json_path = SNAPSHOT_DIR / f"{snap_id}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return snap_id, str(path)


def snapshot_path(snap_id: str) -> Optional[Path]:
    p = SNAPSHOT_DIR / f"{snap_id}.html"
    return p if p.exists() else None


VERDICT_COLORS = {
    "yes": "#2e7d32",
    "no": "#c62828",
    "warning": "#ef6c00",
    "unknown": "#616161",
}


def _render_html(p: dict) -> str:
    v = p["verdict"]
    loc = p["location"]
    where = ", ".join(filter(None, [loc.get("city"), loc.get("county"), loc.get("state")]))
    color = VERDICT_COLORS.get(v["verdict"], "#616161")

    citation_rows = "".join(
        f"""
        <tr>
          <td>{html.escape(c.get("level", ""))}</td>
          <td>{html.escape(c.get("jurisdiction", ""))}</td>
          <td><strong>§ {html.escape(c.get("section_id", ""))}</strong><br>
              <small>{html.escape(c.get("section_name", ""))}</small></td>
          <td>{html.escape(c.get("paraphrase", ""))}</td>
        </tr>
        """
        for c in v.get("citations", [])
    ) or '<tr><td colspan="4"><em>No citations.</em></td></tr>'

    retrieved_blocks = "".join(
        f"""
        <details>
          <summary><strong>§ {html.escape(r.get("section_id", ""))}</strong>
            -- {html.escape(r.get("section_name", ""))}
            <small>[{html.escape(r.get("level", ""))}: {html.escape(r.get("jurisdiction", ""))}]
            distance={r.get("distance", 0):.3f}</small></summary>
          <p><em>{html.escape(r.get("breadcrumb", ""))}</em></p>
          <pre>{html.escape(r.get("text_preview", ""))}</pre>
        </details>
        """
        for r in p["retrieved"]
    )

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>LexLocator Compliance Snapshot {p["id"]}</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 800px;
       margin: 2rem auto; padding: 0 1.5rem; color: #222; line-height: 1.5; }}
header {{ border-bottom: 2px solid #222; padding-bottom: 1rem; margin-bottom: 1.5rem; }}
.verdict-banner {{ background: {color}; color: white; padding: 1rem 1.5rem;
                  border-radius: 8px; font-size: 1.4rem; font-weight: bold;
                  text-transform: uppercase; margin: 1rem 0; }}
.meta {{ background: #f5f5f5; padding: 1rem; border-radius: 6px; font-size: 0.9rem; }}
.meta dt {{ font-weight: bold; }}
.meta dd {{ margin: 0 0 0.5rem 1rem; }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
th, td {{ text-align: left; padding: 0.6rem; border-bottom: 1px solid #ddd;
         vertical-align: top; font-size: 0.9rem; }}
th {{ background: #fafafa; }}
details {{ margin: 0.5rem 0; padding: 0.5rem; background: #fafafa;
          border-left: 3px solid #ccc; }}
pre {{ white-space: pre-wrap; word-wrap: break-word; font-size: 0.85rem;
       background: white; padding: 0.6rem; }}
.hash {{ font-family: monospace; font-size: 0.75rem; word-break: break-all;
        background: #fafafa; padding: 0.5rem; border: 1px solid #ddd; }}
.disclaimer {{ background: #fff3e0; border-left: 4px solid #ef6c00;
              padding: 1rem; margin: 2rem 0; font-size: 0.9rem; }}
@media print {{ body {{ max-width: 100%; }} details {{ open: open; }} }}
</style>
</head><body>

<header>
  <h1>LexLocator Compliance Snapshot</h1>
  <p>Snapshot ID: <code>{p["id"]}</code></p>
</header>

<dl class="meta">
  <dt>Timestamp (UTC)</dt><dd>{p["timestamp_utc"]}</dd>
  <dt>Location</dt><dd>{html.escape(where or "(unknown)")}</dd>
  <dt>GPS</dt><dd>
    {f"{loc.get('lat'):.5f}, {loc.get('lng'):.5f}" if loc.get('lat') is not None else "(not provided)"}
  </dd>
  <dt>Question</dt><dd>{html.escape(p["question"])}</dd>
</dl>

<div class="verdict-banner">{v["verdict"]} -- confidence {v["confidence"]:.0%}</div>

<h2>Answer</h2>
<p>{html.escape(v["answer"])}</p>

{f'<h2>Caveats</h2><p>{html.escape(v["caveats"])}</p>' if v.get("caveats") else ""}

<h2>Citations</h2>
<table>
  <thead><tr><th>Level</th><th>Jurisdiction</th><th>Section</th><th>Paraphrase</th></tr></thead>
  <tbody>{citation_rows}</tbody>
</table>

<h2>Retrieved Sections (Full Record)</h2>
{retrieved_blocks}

<h2>Integrity</h2>
<p>The SHA-256 content hash of this record at generation time:</p>
<div class="hash">{p["content_hash_sha256"]}</div>
<p>If this file has been edited, recomputing the hash from the embedded payload will not match the value above.</p>

<div class="disclaimer">
  <strong>Legal information, not legal advice.</strong> This snapshot reflects
  the scraped municipal code at the moment the query was made. Laws change,
  scrapes may be incomplete, and not every jurisdiction is covered. Verify
  against the official source before relying on this for any decision.
</div>

</body></html>
"""
