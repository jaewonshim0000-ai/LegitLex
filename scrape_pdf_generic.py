"""
Generic outline-aware PDF scraper for legal documents that DON'T use the
Municode "Sec. X-Y" formats — e.g. older zoning ordinances organized as
ARTICLE I / ARTICLE II with numbered sub-sections.

It segments the text by ARTICLE headings (roman numerals) and numbered section
headings ("4. Interpretation...", "Section 10.10."), tracking the current
article as a breadcrumb. Output matches ordinance_scraper.py's shape and is
written to data/, so enrich.py (via jurisdictions.json) tags it like everything
else.

Usage:
  python scrape_pdf_generic.py --pdf "Zoning.pdf" --name montgomery_zoning --out data
  python enrich.py
  python ingest.py
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

import pdfplumber

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROMAN = r"[IVXLCDM]+"
# Real ARTICLE heading (uppercase, short, no dot-leaders from a table of contents)
ART_RE = re.compile(rf"^ARTICLE\s+({ROMAN})\b\.?\s*(.*)$")
# Numbered section heading: "4. Title", "10.10. Title", "Section 3. Title"
SEC_RE = re.compile(r"^(\d+(?:\.\d+)*)\.\s+([A-Z][A-Za-z].{2,90})$")
SEC_WORD_RE = re.compile(r"^Section\s+(\d+(?:\.\d+)*)\.?\s*(.*)$", re.I)
DOT_LEADER = re.compile(r"\.{4,}")   # marks table-of-contents lines


def clean(s: str) -> str:
    return re.sub(r"[ \t]+", " ", s).strip()


def scrape(pdf_path: str, skip_pages: int) -> list[dict]:
    article = ""          # e.g. "VI"
    article_name = ""     # e.g. "GENERAL PROVISIONS"
    cur = None            # current section being built
    out = []

    def flush():
        nonlocal cur
        if cur and len(cur["_buf"]) > 0:
            text = clean(" ".join(cur["_buf"]))
            if len(text) >= 25:
                cur["text"] = text
                del cur["_buf"]
                out.append(cur)
        cur = None

    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages):
            if pi < skip_pages:
                continue
            for raw in (page.extract_text() or "").splitlines():
                line = raw.strip()
                if not line or DOT_LEADER.search(line):
                    continue  # skip blanks and table-of-contents leader lines

                m_art = ART_RE.match(line)
                if m_art and len(line) < 70:
                    flush()
                    article = m_art.group(1)
                    article_name = clean(m_art.group(2))
                    continue

                m_sec = SEC_RE.match(line) or SEC_WORD_RE.match(line)
                if m_sec and len(line) < 100:
                    flush()
                    num, name = m_sec.group(1), clean(m_sec.group(2))
                    sid = f"{article}-{num}" if article else num
                    crumb = "Article " + article + (f" {article_name}" if article_name else "") if article else ""
                    cur = {
                        "section_id": sid,
                        "section_name": name.rstrip("."),
                        "page_start": pi + 1,
                        "breadcrumb": crumb,
                        "citations": [],
                        "_buf": [],
                    }
                    continue

                # body text -> current section (or an article preamble bucket)
                if cur is None:
                    if not article:
                        continue
                    cur = {
                        "section_id": f"{article}-0",
                        "section_name": article_name.title() or "General",
                        "page_start": pi + 1,
                        "breadcrumb": "Article " + article + (f" {article_name}" if article_name else ""),
                        "citations": [],
                        "_buf": [],
                    }
                cur["_buf"].append(line)
    flush()

    # dedupe ids (a number can repeat across articles only if article missing)
    seen = {}
    for r in out:
        sid = r["section_id"]
        if sid in seen:
            seen[sid] += 1
            r["section_id"] = f"{sid}#{seen[sid]}"
        else:
            seen[sid] = 0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--name", required=True, help="Output stem; must match a jurisdictions.json key")
    ap.add_argument("--out", default="data")
    ap.add_argument("--skip-pages", type=int, default=0,
                    help="Skip leading pages (cover/table of contents)")
    args = ap.parse_args()

    recs = scrape(args.pdf, args.skip_pages)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^\w]", "_", args.name.lower()).strip("_")
    out_path = out_dir / f"{stem}.json"
    out_path.write_text(json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(recs)} sections -> {out_path}")
    print("Next:  python enrich.py   then   python ingest.py")


if __name__ == "__main__":
    main()
