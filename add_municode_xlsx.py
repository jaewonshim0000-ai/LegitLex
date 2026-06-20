"""
Add ANY city or county code to the dataset from a Municode XLSX export.

Most U.S. city/county codes live on Municode (library.municode.com). Use the
site's Download/Export to get an .xlsx (columns: Url, NodeId, Title, Subtitle,
Content), then run this to tag + convert it into the enriched JSON shape
ingest.py consumes. Works for both city and county codes.

Examples:
  # A city code:
  python add_municode_xlsx.py --xlsx "C:/.../SanDiego.xlsx" --level city \
      --city "San Diego" --county "San Diego County" --state CA \
      --name "San Diego Municipal Code"

  # A county code:
  python add_municode_xlsx.py --xlsx "C:/.../LACounty.xlsx" --level county \
      --county "Los Angeles County" --state CA \
      --name "Los Angeles County Code"

Then:  python ingest.py

(The retrieval filter auto-includes this data when a user's GPS resolves to that
city/county/state — no other code changes needed.)
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

import openpyxl

TOO_LARGE = "Content is too large for cell."
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
    return re.sub(r"[ \t ]+", " ", s).replace(" \n", "\n").strip()


def head_level(title: str):
    for rx, lvl in HEAD_LEVELS:
        if rx.match(title):
            return lvl
    return None


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--level", required=True, choices=["city", "county"])
    ap.add_argument("--city", default="")
    ap.add_argument("--county", default="")
    ap.add_argument("--state", required=True, help="2-letter state code, e.g. CA")
    ap.add_argument("--name", required=True, help="Source title, e.g. 'San Diego Municipal Code'")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    state = args.state.strip().upper()
    place = args.city or args.county
    if not place:
        raise SystemExit("Provide --city (for level=city) or --county (for level=county).")
    source_file = f"{args.level}_{slug(place)}"
    out_path = Path(args.out) if args.out else Path("data_enriched") / f"{source_file}.json"

    wb = openpyxl.load_workbook(args.xlsx, read_only=True)
    ws = wb.active
    crumbs = ["", "", "", ""]
    records = []
    seen_ids: dict[str, int] = {}

    for url, nid, title, sub, content in ws.iter_rows(min_row=3, values_only=True):
        title = (title or "").strip()
        content = (content or "").strip()
        if not title:
            continue
        lvl = head_level(title)
        is_leaf = content and content != TOO_LARGE
        if lvl is not None and not is_leaf:
            crumbs[lvl] = re.sub(r"\s+", " ", title)
            for d in range(lvl + 1, 4):
                crumbs[d] = ""
            continue
        if not is_leaf:
            continue

        m = SEC_RE.match(title) or NUM_RE.match(title)
        sid = m.group(1).rstrip(".") if m else re.sub(r"\s+", "_", title)[:24]
        if sid in seen_ids:
            seen_ids[sid] += 1
            sid = f"{sid}#{seen_ids[sid]}"
        else:
            seen_ids[sid] = 0

        text = clean(content)
        if len(text) < 15:
            continue

        records.append({
            "section_id": sid,
            "section_name": re.sub(r"^Sec\.\s*[0-9A-Za-z.\-]+\.?\s*", "", title).strip(),
            "text": text,
            "page_start": 0,
            "breadcrumb": " > ".join([c for c in crumbs if c]) or args.name,
            "citations": [],
            "jurisdiction": {
                "level": args.level,
                "city": args.city,
                "county": args.county,
                "state": state,
                "country": "US",
                "source_title": args.name,
                "source_url": url or "",
            },
            "source_file": source_file,
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(records)} {args.level} sections for {place}, {state} -> {out_path}")
    print("Next:  python ingest.py")


if __name__ == "__main__":
    main()
