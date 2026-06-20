"""
Fetch federal rulemaking documents from the Regulations.gov API (v4) and write
them in the enriched JSON shape ingest.py consumes, tagged level=federal.

NOTE: Regulations.gov covers the rulemaking PIPELINE — proposed rules, final
rule notices, dockets and public comments — NOT the codified CFR text (you
already have that via fetch_federal.py / eCFR). This adds regulatory *activity*
and context, and is what powers "new / proposed federal rule" alerts.

Setup:
  1. You already have a key from https://open.gsa.gov/api/regulationsgov/
  2. Add it to .env:   REGULATIONS_GOV_API_KEY=your-key
  3. python fetch_federal_regsgov.py
  4. python ingest.py

Docs: https://open.gsa.gov/api/regulationsgov/
"""
from __future__ import annotations
import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

from lexlocator import config  # noqa: F401  (loads .env)

API = "https://api.regulations.gov/v4/documents"
OUT_DIR = Path("data_enriched")
OUT_FILE = OUT_DIR / "federal_regulationsgov.json"

# Topic -> search term used against Regulations.gov full text.
REG_TOPICS = [
    ("drones", "unmanned aircraft systems"),
    ("ebikes", "low-speed electric bicycle"),
    ("service_animals", "service animals"),
    ("noise", "noise control"),
]

# Document types worth ingesting (skip pure notices/comments by default).
KEEP_TYPES = {"Rule", "Proposed Rule"}
MAX_PER_TOPIC = 5


def _key() -> str:
    k = os.environ.get("REGULATIONS_GOV_API_KEY") or os.environ.get("REGS_GOV_API_KEY")
    if not k:
        raise SystemExit("REGULATIONS_GOV_API_KEY not set. Add it to .env.")
    return k


def search_documents(term: str, page_size: int = 20) -> list[dict]:
    params = {
        "filter[searchTerm]": term,
        "sort": "-postedDate",
        "page[size]": page_size,
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "X-Api-Key": _key(),
        "User-Agent": "lexlocator",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return data.get("data", [])


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", s).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-per-topic", type=int, default=MAX_PER_TOPIC)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sections = []
    seen = set()

    for topic, term in REG_TOPICS:
        print(f"\nTopic '{topic}'  term='{term}'")
        try:
            docs = search_documents(term)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:200]
            print(f"  HTTP {e.code}: {body}")
            continue
        except Exception as e:
            print(f"  error: {e}")
            continue

        kept = 0
        for d in docs:
            if kept >= args.max_per_topic:
                break
            attr = d.get("attributes", {})
            dtype = attr.get("documentType", "")
            if dtype not in KEEP_TYPES:
                continue
            doc_id = d.get("id", "")
            if not doc_id or doc_id in seen:
                continue

            title = strip_html(attr.get("title", ""))
            snippet = strip_html(attr.get("highlightedContent", ""))
            agency = attr.get("agencyId", "")
            posted = (attr.get("postedDate", "") or "")[:10]
            fr = attr.get("frDocNum", "")
            open_comment = attr.get("openForComment", False)

            text_bits = [title]
            if snippet:
                text_bits.append(snippet)
            text_bits.append(
                f"Document type: {dtype}. Agency: {agency}. Posted: {posted}."
                + (" Currently open for public comment." if open_comment else "")
            )
            text = " ".join(b for b in text_bits if b)
            if len(text) < 40:
                continue

            seen.add(doc_id)
            kept += 1
            sections.append({
                "section_id": fr or doc_id,
                "section_name": f"[{dtype}] {title}"[:200],
                "text": text,
                "page_start": 0,
                "breadcrumb": f"Federal Register > {agency} > {dtype}",
                "citations": [c for c in [fr, doc_id] if c],
                "topic": topic,
                "jurisdiction": {
                    "level": "federal",
                    "city": "",
                    "county": "",
                    "state": "",
                    "country": "US",
                    "source_title": f"Regulations.gov — {dtype} ({agency})",
                    "source_url": f"https://www.regulations.gov/document/{doc_id}",
                },
                "source_file": "federal_regulationsgov",
            })
            flag = "  [OPEN FOR COMMENT]" if open_comment else ""
            print(f"  + {dtype}: {title[:64]}{flag}")
            time.sleep(0.3)

    OUT_FILE.write_text(json.dumps(sections, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nWrote {len(sections)} federal rulemaking docs -> {OUT_FILE}")
    print("Next:  python ingest.py")


if __name__ == "__main__":
    main()
