"""
Fetch federal STATUTES (US Code) from the official GovInfo / GPO service and
write them in the enriched JSON shape ingest.py consumes, tagged level=federal.

This supersedes the Cornell-LII scraper (fetch_us_code.py) with official U.S.
Government Publishing Office content. Two modes:

  CURATED (default): fetch a hand-picked list of US Code sections (USC_SECTIONS).
      python fetch_govinfo.py

  SEARCH (uses your GovInfo API key): discover sections across ALL of the US
  Code by topic and ingest the top matches.
      python fetch_govinfo.py --search "racial discrimination public accommodation"
      python fetch_govinfo.py --search "firearm possession" --max 8

Then:  python ingest.py

Key: set GOVINFO_API_KEY in .env (an api.data.gov key — your Regulations.gov key
also works, since api.data.gov keys are universal). Get one at
https://api.data.gov/signup/  or  https://www.govinfo.gov/api-signup
Docs: https://api.govinfo.gov/docs/
"""
from __future__ import annotations
import argparse
import json
import os
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

from lexlocator import config  # noqa: F401  (loads .env)

OUT_DIR = Path("data_enriched")
OUT_FILE = OUT_DIR / "federal_us_code.json"      # overwrites the LII output
LINK = "https://www.govinfo.gov/link/uscode/{title}/{section}?link-type=html"
CONTENT = "https://www.govinfo.gov/content/pkg/{pkg}/html/{granule}.htm"
SEARCH = "https://api.govinfo.gov/search"

# Curated US Code sections (title, section, topic). Extend freely.
USC_SECTIONS = [
    ("42", "2000a",   "civil_rights"),   # Title II CRA — public accommodations
    ("42", "2000a-1", "civil_rights"),
    ("42", "2000a-2", "civil_rights"),
    ("42", "2000a-3", "civil_rights"),
    ("42", "2000d",   "civil_rights"),   # Title VI — federally funded programs
    ("42", "2000e-2", "civil_rights"),   # Title VII — employment
    ("42", "1981",    "civil_rights"),   # equal rights / contracts
    ("42", "3604",    "civil_rights"),   # Fair Housing Act
    ("42", "12182",   "civil_rights"),   # ADA Title III — public accommodations
]

NOTE_MARKERS = ["Editorial Notes", "Statutory Notes", "Amendments",
                "Effective Date", "U.S. Code Toolbox", "References in Text"]


def api_key() -> str | None:
    return os.environ.get("GOVINFO_API_KEY") or os.environ.get("REGULATIONS_GOV_API_KEY")


def _fetch(url: str, data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(url, data=data,
                                 headers=headers or {"User-Agent": "lexlocator"})
    return urllib.request.urlopen(req, timeout=60)


def parse_content(html: str, granule_id: str, topic: str) -> dict | None:
    # citation from granule id: ...title42...sec2000a
    m = re.search(r"title(\w+).*?sec([\w-]+)", granule_id, re.I)
    title = m.group(1) if m else "?"
    section = m.group(2) if m else "?"

    flat = re.sub("<[^>]+>", " ", html)
    flat = flat.replace("&sect;", "§").replace("&amp;", "&").replace("&#167;", "§")
    flat = re.sub(r"\s+", " ", flat).strip()

    # name: "Sec. 2000a - <name> From the U.S. Government Publishing Office"
    nm = re.search(r"Sec\.\s*[\w-]+\s*[-–]\s*(.*?)\s+From the U\.S\.", flat)
    name = nm.group(1).strip() if nm else ""

    # body: everything after the GPO provenance line
    k = flat.find("www.gpo.gov")
    body = flat[k + len("www.gpo.gov"):].strip() if k != -1 else flat
    for mk in NOTE_MARKERS:
        j = body.find(mk)
        if j != -1:
            body = body[:j]
    body = body.strip()
    if len(body) < 60:
        return None

    return {
        "section_id": f"{title} U.S.C. § {section}",
        "section_name": name,
        "text": body,
        "page_start": 0,
        "breadcrumb": f"United States Code > Title {title} > § {section}",
        "citations": [f"{title} U.S.C. {section}"],
        "topic": topic,
        "jurisdiction": {
            "level": "federal", "city": "", "county": "", "state": "",
            "country": "US",
            "source_title": f"{title} U.S.C. § {section} (GovInfo/GPO)",
            "source_url": CONTENT.format(pkg=f"USCODE-2024-title{title}", granule=granule_id),
        },
        "source_file": "federal_us_code",
    }


def fetch_citation(title: str, section: str, topic: str) -> dict | None:
    """Resolve a citation via the GovInfo link service and parse the content."""
    try:
        r = _fetch(LINK.format(title=title, section=section))
        final = r.geturl()
        html = r.read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"  ERROR {title} USC {section}: {e}")
        return None
    gm = re.search(r"/html/([^/]+)\.htm", final)
    granule = gm.group(1) if gm else f"title{title}-sec{section}"
    return parse_content(html, granule, topic)


def search_uscode(query: str, max_results: int) -> list[dict]:
    """Use the GovInfo search API (needs key) to find US Code granules."""
    key = api_key()
    if not key:
        raise SystemExit("GOVINFO_API_KEY not set (and no REGULATIONS_GOV_API_KEY). Add to .env.")
    body = json.dumps({
        "query": f"collection:USCODE AND {query}",
        "pageSize": max_results,
        "offsetMark": "*",
        "sorts": [{"field": "relevancy", "sortOrder": "DESC"}],
    }).encode()
    r = _fetch(f"{SEARCH}?api_key={key}", data=body,
               headers={"Content-Type": "application/json", "User-Agent": "lexlocator"})
    results = json.load(r).get("results", [])
    out = []
    for res in results:
        gid = res.get("granuleId")
        pkg = res.get("packageId")
        if not gid or not pkg:
            continue
        try:
            html = _fetch(CONTENT.format(pkg=pkg, granule=gid)).read().decode("utf-8", "ignore")
        except Exception:
            continue
        rec = parse_content(html, gid, "search")
        if rec:
            out.append(rec)
        time.sleep(0.3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", help="Topic to search across all US Code")
    ap.add_argument("--max", type=int, default=6, help="Max results for --search")
    ap.add_argument("--append", action="store_true",
                    help="Merge with existing federal_us_code.json instead of overwriting")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []

    if args.search:
        print(f"GovInfo search: '{args.search}'")
        records = search_uscode(args.search, args.max)
    else:
        print("Fetching curated US Code sections from GovInfo/GPO...")
        for title, section, topic in USC_SECTIONS:
            rec = fetch_citation(title, section, topic)
            if rec:
                records.append(rec)
                print(f"  + {rec['section_id']}  {rec['section_name'][:55]}")
            time.sleep(0.4)

    if args.append and OUT_FILE.exists():
        existing = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        by_id = {r["section_id"]: r for r in existing}
        for r in records:
            by_id[r["section_id"]] = r
        records = list(by_id.values())

    OUT_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(records)} US Code sections -> {OUT_FILE}")
    print("Next:  python ingest.py")


if __name__ == "__main__":
    main()
