"""
Scrape the Code of Alabama from the official Alabama Legislature site
(alison.legislature.state.al.us) via its GraphQL API, and write the result in
the enriched JSON shape ingest.py consumes, tagged level=state (state=AL).

Alabama organizes its code by numbered TITLES (not CA-style named codes). This
maps the requested CA-style abbreviations to Alabama Titles:

    VEH -> Title 32   Motor Vehicles and Traffic
    PEN -> Title 13A  Criminal Code
    CIV -> Title 6    Civil Practice
    HSC -> Title 22   Health, Mental Health, and Environmental Control

How it works:
  1. codeOfAlabamaTitles  -> the full hierarchy; we find each Title's codeId
  2. CodeOfAlabamaPrintContent(include:[codeId]) -> ALL sections under that title
     in a single call (displayId, catchLine, content, history)

Usage:
  python scrape_al_code.py                       # the 4 key codes above
  python scrape_al_code.py --codes VEH,PEN       # subset
  python scrape_al_code.py --titles 32,13A       # by Alabama title number
Then:
  python ingest.py
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "https://alison.legislature.state.al.us"
GQL = BASE + "/graphql"
OUT_DIR = Path("data_enriched")
DAGGER, INTEGRAL = "†", "∫"   # field / record separators in titles blob

# CA-style abbreviation -> Alabama Title number (as shown in "Title NN ...")
CODE_TO_TITLE = {
    "VEH": "32", "PEN": "13A", "CIV": "6", "HSC": "22",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 Chrome/124.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": BASE,
    "Referer": BASE + "/code-of-alabama",
}

PRINT_QUERY = (
    "query CodeOfAlabamaPrintContent($include:[ID!]){"
    " sections: codesOfAlabama(where:{type:{eq:Section}}, include:$include, versions:true){"
    " data{ displayId catchLine content history effectiveDate supersessionDate } } }"
)


def gql(query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(GQL, data=body, headers=HEADERS), timeout=90) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def title_codeids() -> dict:
    """Return {title_number: (codeId, full_title_name)} for every Title."""
    raw = gql("query { titles: codeOfAlabamaTitles }")["data"]["titles"]
    out = {}
    for rec in raw.split(INTEGRAL):
        f = rec.split(DAGGER)
        if len(f) < 2 or not f[0].strip():
            continue
        cid, name = f[0].strip(), f[1].strip()
        m = re.match(r"Title (\w+)\s", name)
        if m:
            out[m.group(1)] = (cid, name)
    return out


def clean(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&sect;", "§").replace("&amp;", "&").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()


def fetch_title(code_id: str, title_name: str) -> list[dict]:
    data = gql(PRINT_QUERY, {"include": [code_id]})
    secs = (((data or {}).get("data") or {}).get("sections") or {}).get("data") or []

    # The API returns multiple VERSIONS per section (current + superseded).
    # Keep one per displayId: prefer the non-superseded / latest effectiveDate.
    best: dict[str, dict] = {}
    for s in secs:
        did = (s.get("displayId") or "").strip()
        if not did:
            continue
        prev = best.get(did)
        if prev is None:
            best[did] = s
            continue
        # prefer the one still in effect (no supersessionDate), else later effectiveDate
        s_live = not s.get("supersessionDate")
        p_live = not prev.get("supersessionDate")
        if s_live and not p_live:
            best[did] = s
        elif s_live == p_live and (s.get("effectiveDate") or "") > (prev.get("effectiveDate") or ""):
            best[did] = s

    out = []
    for did, s in best.items():
        text = clean(s.get("content") or "")
        if len(text) < 20:
            continue
        hist = clean(s.get("history") or "")
        out.append({
            "section_id": f"AL § {did}",
            "section_name": clean(s.get("catchLine") or ""),
            "text": text + (f"  History: {hist}" if hist else ""),
            "page_start": 0,
            "breadcrumb": title_name,
            "citations": [hist] if hist else [],
            "jurisdiction": {
                "level": "state", "city": "", "county": "",
                "state": "AL", "country": "US",
                "source_title": f"Code of Alabama — {title_name}",
                "source_url": f"{BASE}/code-of-alabama",
            },
            "source_file": f"state_al_{title_name.split()[1].lower()}",
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default="VEH,PEN,CIV,HSC",
                    help="CA-style abbreviations (mapped to AL titles)")
    ap.add_argument("--titles", default="", help="AL title numbers directly, e.g. 32,13A")
    args = ap.parse_args()

    if args.titles.strip():
        want = [t.strip().upper() for t in args.titles.split(",")]
    else:
        want = [CODE_TO_TITLE[c.strip().upper()] for c in args.codes.split(",")
                if c.strip().upper() in CODE_TO_TITLE]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Fetching Alabama code hierarchy...")
    titles = title_codeids()

    grand = 0
    for tnum in want:
        info = titles.get(tnum)
        if not info:
            print(f"  ! Title {tnum} not found")
            continue
        cid, name = info
        print(f"  Title {tnum}: {name}  (codeId {cid}) ...")
        try:
            recs = fetch_title(cid, name)
        except Exception as e:
            print(f"    ERROR: {e}")
            continue
        out_path = OUT_DIR / f"state_al_title{tnum.lower()}.json"
        out_path.write_text(json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")
        grand += len(recs)
        print(f"    {len(recs)} sections -> {out_path.name}")
        time.sleep(0.6)

    print(f"\nDone. {grand} Alabama sections written to {OUT_DIR}/.")
    print("Next:  python ingest.py")


if __name__ == "__main__":
    main()
