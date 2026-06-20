"""
Fetch enacted California legislation from the LegiScan API and write it in the
enriched JSON shape ingest.py consumes, tagged level=state.

LegiScan indexes BILLS (legislation), not the consolidated codes — but the text
of an enacted (chaptered) bill contains the actual statutory language, so it's
usable for RAG verdicts and also powers "new law" alerts.

Setup:
  1. Get a free API key at https://legiscan.com/legiscan  (Account -> API)
  2. Add it to .env:   LEGISCAN_API_KEY=your-key
  3. python fetch_state_legiscan.py
  4. python ingest.py

Docs: https://legiscan.com/gaits/documentation/legiscan
"""
from __future__ import annotations
import argparse
import base64
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from lexlocator import config  # noqa: F401  (loads .env)

API = "https://api.legiscan.com/"
OUT_DIR = Path("data_enriched")
OUT_FILE = OUT_DIR / "state_ca_legiscan.json"

# Topic -> search query. Tune these; LegiScan relevance-ranks full-text.
DEFAULT_TOPICS = [
    ("ebikes", "electric bicycle"),
    ("drones", "unmanned aircraft drone"),
    ("dogs", "dog leash animal control"),
    ("noise", "noise ordinance"),
    ("civil_rights", "discrimination public accommodation"),
]

# Full state name for breadcrumbs/source titles.
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

MAX_BILLS_PER_TOPIC = 3      # keep it small + relevant
MAX_TEXT_CHARS = 20000       # cap huge bill blobs (ingest chunks them anyway)
PASSED_STATUS = 4            # LegiScan: 4 = Passed/Chaptered


def _key() -> str:
    k = os.environ.get("LEGISCAN_API_KEY")
    if not k:
        raise SystemExit("LEGISCAN_API_KEY not set. Add it to .env (see file header).")
    return k


def api_call(op: str, **params) -> dict:
    params.update({"key": _key(), "op": op})
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "lexlocator"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if data.get("status") != "OK":
        raise RuntimeError(f"LegiScan {op} error: {data.get('alert') or data}")
    return data


def search(query: str, state: str) -> list[dict]:
    """Full-text search within the state. Returns ranked bill stubs."""
    data = api_call("getSearch", state=state, query=query)
    res = data.get("searchresult", {})
    # searchresult has a 'summary' key plus numbered entries "0","1",...
    return [v for k, v in res.items() if k.isdigit()]


def get_bill(bill_id: int) -> dict:
    return api_call("getBill", id=bill_id).get("bill", {})


def get_bill_text(doc_id: int) -> tuple[str, str]:
    """Return (mime_type, decoded_text) for a bill document."""
    t = api_call("getBillText", id=doc_id).get("text", {})
    mime = t.get("mime", "")
    raw = base64.b64decode(t.get("doc", "")) if t.get("doc") else b""
    return mime, _extract_text(mime, raw)


def _extract_text(mime: str, raw: bytes) -> str:
    if not raw:
        return ""
    if "pdf" in mime:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                return "\n".join((p.extract_text() or "") for p in pdf.pages)
        except Exception:
            return ""
    # html or plain text
    txt = raw.decode("utf-8", "ignore")
    if "<" in txt and ">" in txt:
        txt = re.sub(r"(?is)<(script|style).*?</\1>", " ", txt)
        txt = re.sub(r"<[^>]+>", " ", txt)
    return txt


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def pick_text_doc(bill: dict) -> int | None:
    """Choose the most authoritative text: Chaptered > Enrolled > latest."""
    texts = bill.get("texts", []) or []
    if not texts:
        return None
    order = {"Chaptered": 3, "Enrolled": 2, "Amended": 1, "Introduced": 0}
    texts = sorted(texts, key=lambda t: order.get(t.get("type", ""), 0), reverse=True)
    return texts[0].get("doc_id")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="CA", help="2-letter state code, e.g. TX, NY")
    ap.add_argument("--topics", default="",
                    help="Optional 'topic:query' pairs, comma-separated. "
                         "Default = built-in topic set.")
    ap.add_argument("--max-per-topic", type=int, default=MAX_BILLS_PER_TOPIC)
    args = ap.parse_args()

    state = args.state.strip().upper()
    state_name = STATE_NAMES.get(state, state)
    out_file = OUT_DIR / f"state_{state.lower()}_legiscan.json"
    if args.topics.strip():
        topics = [(p.split(":", 1)[0].strip(), p.split(":", 1)[1].strip())
                  for p in args.topics.split(",") if ":" in p]
    else:
        topics = DEFAULT_TOPICS

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sections = []
    seen_bills = set()

    for topic, query in topics:
        print(f"\nTopic '{topic}'  query='{query}'")
        try:
            stubs = search(query, state)
        except Exception as e:
            print(f"  search failed: {e}")
            continue

        kept = 0
        for stub in stubs:
            if kept >= args.max_per_topic:
                break
            bill_id = stub.get("bill_id")
            if not bill_id or bill_id in seen_bills:
                continue
            try:
                bill = get_bill(bill_id)
            except Exception as e:
                print(f"  getBill {bill_id} failed: {e}")
                continue

            if bill.get("status") != PASSED_STATUS:
                continue  # only enacted/chaptered law
            doc_id = pick_text_doc(bill)
            if not doc_id:
                continue
            try:
                mime, text = get_bill_text(doc_id)
            except Exception as e:
                print(f"  getBillText {doc_id} failed: {e}")
                continue
            text = clean(text)[:MAX_TEXT_CHARS]
            if len(text) < 80:
                continue

            seen_bills.add(bill_id)
            kept += 1
            num = bill.get("bill_number", str(bill_id))
            year = (bill.get("session", {}) or {}).get("year_start", "")
            sections.append({
                "section_id": f"{state} {num}" + (f" ({year})" if year else ""),
                "section_name": clean(bill.get("title", "")),
                "text": text,
                "page_start": 0,
                "breadcrumb": f"{state_name} Legislature > {topic}",
                "citations": [clean(bill.get("bill_number", ""))],
                "topic": topic,
                "jurisdiction": {
                    "level": "state",
                    "city": "",
                    "county": "",
                    "state": state,
                    "country": "US",
                    "source_title": f"{state_name} {num} (enacted)",
                    "source_url": bill.get("state_link") or bill.get("url", ""),
                },
                "source_file": f"state_{state.lower()}_legiscan",
            })
            print(f"  + {num}: {clean(bill.get('title',''))[:70]}")
            time.sleep(0.4)  # be polite

    out_file.write_text(json.dumps(sections, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nWrote {len(sections)} enacted {state} bills -> {out_file}")
    print("Next:  python ingest.py")


if __name__ == "__main__":
    main()
