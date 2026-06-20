"""
Fetch targeted United States Code STATUTES and write them in the enriched JSON
shape ingest.py consumes, tagged level=federal.

WHY THIS EXISTS: eCFR only has *regulations* (CFR); Regulations.gov only has
rulemaking *documents*. Neither contains federal *statutes* (the US Code) — yet
many real questions (e.g. "a restaurant refuses service based on race") are
answered by a statute: Title II of the Civil Rights Act of 1964, 42 U.S.C.
2000a. This fetcher fills that gap.

Source: Cornell Legal Information Institute (law.cornell.edu) — public-domain
US Code text sourced from the Office of Law Revision Counsel. Keyless.

Usage:
    python fetch_us_code.py
    python ingest.py
"""
from __future__ import annotations
import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

OUT_DIR = Path("data_enriched")
OUT_FILE = OUT_DIR / "federal_us_code.json"
BASE = "https://www.law.cornell.edu/uscode/text"

# Curated US Code sections. (title, section, topic). Easy to extend.
USC_SECTIONS = [
    # Civil rights — public accommodations (the restaurant/race case)
    ("42", "2000a",   "civil_rights"),   # Title II CRA — equal access
    ("42", "2000a-1", "civil_rights"),   # prohibition under law/ordinance
    ("42", "2000a-2", "civil_rights"),   # prohibition on deprivation/intimidation
    ("42", "2000a-3", "civil_rights"),   # enforcement / civil action
    # Other major anti-discrimination statutes (commonly asked)
    ("42", "2000d",   "civil_rights"),   # Title VI — federally funded programs
    ("42", "2000e-2", "civil_rights"),   # Title VII — employment
    ("42", "1981",    "civil_rights"),   # equal rights / contracts (race)
    ("42", "3604",    "civil_rights"),   # Fair Housing Act — housing
    ("42", "12182",   "civil_rights"),   # ADA Title III — public accommodations (disability)
]

NOTE_MARKERS = [
    "Editorial Notes", "Statutory Notes", "U.S. Code Toolbox",
    "References in Text", "Amendments", "Effective Date",
]


def fetch(title: str, section: str) -> dict | None:
    url = f"{BASE}/{title}/{section}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 lexlocator"})
    try:
        html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"  ERROR {title} USC {section}: {e}")
        return None

    # Title/name from the H1
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    h1 = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", m.group(1))).strip() if m else ""
    name = h1.split(" - ", 1)[1].strip() if " - " in h1 else h1

    # Body from the content container
    i = html.find('id="content"')
    seg = html[i:i + 60000] if i != -1 else html
    seg = re.sub(r"(?is)<(script|style|nav).*?</\1>", " ", seg)
    txt = re.sub("<[^>]+>", " ", seg)
    txt = re.sub(r"\s+", " ", txt).strip()

    j = txt.find("prev | next")
    if j != -1:
        txt = txt[j + len("prev | next"):]
    # also drop the repeated H1 title if present at the start
    if name and name in txt[:len(name) + 80]:
        txt = txt[txt.find(name) + len(name):]
    for mk in NOTE_MARKERS:
        k = txt.find(mk)
        if k != -1:
            txt = txt[:k]
    body = txt.strip()
    if len(body) < 60:
        print(f"  WARN  {title} USC {section}: body too short, skipping")
        return None

    return {
        "section_id": f"{title} U.S.C. § {section}",
        "section_name": name,
        "text": body,
        "page_start": 0,
        "breadcrumb": f"United States Code > Title {title} > § {section}",
        "citations": [f"{title} U.S.C. {section}"],
        "jurisdiction": {
            "level": "federal",
            "city": "",
            "county": "",
            "state": "",
            "country": "US",
            "source_title": f"{title} U.S.C. § {section} (United States Code)",
            "source_url": url,
        },
        "source_file": "federal_us_code",
    }


def main():
    argparse.ArgumentParser().parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for title, section, topic in USC_SECTIONS:
        rec = fetch(title, section)
        if rec:
            rec["topic"] = topic
            out.append(rec)
            print(f"  + {rec['section_id']}  {rec['section_name'][:60]}")
        time.sleep(0.5)
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(out)} US Code sections -> {OUT_FILE}")
    print("Next:  python ingest.py")


if __name__ == "__main__":
    main()
