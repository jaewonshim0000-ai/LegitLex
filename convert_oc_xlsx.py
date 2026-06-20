"""
Convert the Municode 'Orange County Code of Ordinances' XLSX export into the
enriched JSON shape ingest.py consumes, tagged level=county.

Why not scrape Municode? library.municode.com is a JavaScript app; its export
(File -> Download/Export from Municode) already gives clean, structured content.
That export is what we use here — more reliable than scraping the SPA.

Input : the .xlsx export (columns: Url, NodeId, Title, Subtitle, Content)
Output: data_enriched/county_oc.json
Then  : python ingest.py

Usage:
  python convert_oc_xlsx.py --xlsx "C:/Users/New Owner/Downloads/OrangeCountyCACodeofOrdinancesEXPORT20260609.xlsx"
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

import openpyxl

OUT = Path("data_enriched/county_oc.json")
TOO_LARGE = "Content is too large for cell."

# Heading classifier: maps a leading keyword to a breadcrumb level (0=top).
HEAD_LEVELS = [
    (re.compile(r"^title\b", re.I), 0),
    (re.compile(r"^(division|div\.)\b", re.I), 1),
    (re.compile(r"^part\b", re.I), 1),
    (re.compile(r"^(chapter|chap\.)\b", re.I), 2),
    (re.compile(r"^(article|art\.)\b", re.I), 3),
]
SEC_RE = re.compile(r"^Sec\.\s*([0-9A-Za-z][0-9A-Za-z.\-]*)", re.I)
NUM_RE = re.compile(r"^([0-9]+[0-9A-Za-z.\-]*)")


def clean(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[ \t ]+", " ", s).replace(" \n", "\n").strip()


def head_level(title: str):
    for rx, lvl in HEAD_LEVELS:
        if rx.match(title):
            return lvl
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True, help="Path to the Municode XLSX export")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.xlsx, read_only=True)
    ws = wb.active

    crumbs = ["", "", "", ""]   # title / division-part / chapter / article
    records = []
    seen_ids: dict[str, int] = {}

    for url, nid, title, sub, content in ws.iter_rows(min_row=3, values_only=True):
        title = (title or "").strip()
        content = (content or "").strip()
        if not title:
            continue

        # Heading row -> update breadcrumb, don't emit
        lvl = head_level(title)
        is_leaf = content and content != TOO_LARGE
        if lvl is not None and not is_leaf:
            crumbs[lvl] = re.sub(r"\s+", " ", title)
            for d in range(lvl + 1, 4):
                crumbs[d] = ""
            continue

        if not is_leaf:
            continue  # empty container / oversized aggregate node

        # Section id from the title
        m = SEC_RE.match(title) or NUM_RE.match(title)
        sid = m.group(1).rstrip(".") if m else re.sub(r"\s+", "_", title)[:24]
        # disambiguate collisions (e.g., Charter '101' vs another '101')
        if sid in seen_ids:
            seen_ids[sid] += 1
            sid = f"{sid}#{seen_ids[sid]}"
        else:
            seen_ids[sid] = 0

        breadcrumb = " > ".join([c for c in crumbs if c]) or "Orange County Code of Ordinances"
        text = clean(content)
        if len(text) < 15:
            continue

        records.append({
            "section_id": sid,
            "section_name": re.sub(r"^Sec\.\s*[0-9A-Za-z.\-]+\.?\s*", "", title).strip(),
            "text": text,
            "page_start": 0,
            "breadcrumb": breadcrumb,
            "citations": [],
            "jurisdiction": {
                "level": "county", "city": "", "county": "Orange County",
                "state": "CA", "country": "US",
                "source_title": "Orange County Code of Ordinances",
                "source_url": url or "https://library.municode.com/ca/orange_county",
            },
            "source_file": "county_oc",
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(records)} Orange County sections -> {OUT}")
    print("Next:  python ingest.py")


if __name__ == "__main__":
    main()
