"""
Universal Municipal Code Scraper
=================================
Works across different counties/cities by auto-detecting the section
numbering format used in each PDF.

Supported formats (auto-detected):
  A_irvine     — Sec. 1-2-303  / § 1-2-303        (3-part dash)
  B_dotted3    — Sec. 12.04.010 / § 12.04.010      (3-part dot)
  C_simple2    — Sec. 2-141    / § 2-141            (2-part dash)
  D_bare_dot3  — 15.04.010                          (no Sec. prefix)
  E_dotted2    — Sec. 6.08     / § 6.08             (2-part dot)
  F_plain      — Section 14-32 / Section 14.32      (plain)

Usage:
    python ordinance_scraper.py --pdf MyCounty.pdf
    python ordinance_scraper.py --pdf MyCounty.pdf --name "Orange County"
    python ordinance_scraper.py --pdf MyCounty.pdf --format A_irvine
    python ordinance_scraper.py --pdf MyCounty.pdf --pages 1-500
    python ordinance_scraper.py --pdf MyCounty.pdf --search "noise"
    python ordinance_scraper.py --pdf MyCounty.pdf --detect-only

For very large PDFs (1000+ pages), run in page chunks to stay within memory:
    python ordinance_scraper.py --pdf Big.pdf --pages 1-500    --out output
    python ordinance_scraper.py --pdf Big.pdf --pages 501-1000 --out output
    python ordinance_scraper.py --pdf Big.pdf --pages 1001-    --out output
    (outputs are automatically merged across runs into the same files)
"""

import re
import json
import csv
import argparse
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from collections import Counter

# Windows consoles default to cp1252, which can't print characters like "§" or
# "→" used in status messages. Force UTF-8 so prints never crash mid-run.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    import pdfplumber
    import pypdf
except ImportError:
    print("Missing dependencies. Run:\n  pip install pdfplumber pypdf")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Section format definitions
# ---------------------------------------------------------------------------

SECTION_FORMATS = {
    "A_irvine": {
        "description": "3-part dash  (Sec. 1-2-303 or § 1-2-303)",
        "pattern": re.compile(
            r'(?:Sec(?:tion)?\.?\s*|§\s*)(\d+)-(\d+)-(\d+[A-Za-z]?)[.\s]',
            re.IGNORECASE),
        "id_template": "{0}-{1}-{2}",
    },
    "B_dotted3": {
        "description": "3-part dotted  (Sec. 12.04.010 or § 12.04.010)",
        "pattern": re.compile(
            r'(?:Sec(?:tion)?\.?\s*|§\s*)(\d+)\.(\d+)\.(\d+[A-Za-z]?)[.\s]',
            re.IGNORECASE),
        "id_template": "{0}.{1}.{2}",
    },
    "C_simple2": {
        "description": "2-part dash  (Sec. 2-141 or § 2-141)",
        "pattern": re.compile(
            r'(?:Sec(?:tion)?\.?\s*|§\s*)(\d+)-(\d+[A-Za-z]?)[.\s]',
            re.IGNORECASE),
        "id_template": "{0}-{1}",
    },
    "D_bare_dot3": {
        "description": "Bare 3-part dotted  (15.04.010 — no Sec. prefix)",
        "pattern": re.compile(
            r'(?<!\d)(\d{1,3})\.(\d{2,3})\.(\d{3,4}[A-Za-z]?)(?:[.\s]|$)',
            re.IGNORECASE),
        "id_template": "{0}.{1}.{2}",
    },
    "E_dotted2": {
        "description": "2-part dotted  (Sec. 6.08 or § 6.08)",
        "pattern": re.compile(
            r'(?:Sec(?:tion)?\.?\s*|§\s*)(\d+)\.(\d+[A-Za-z]?)[.\s]',
            re.IGNORECASE),
        "id_template": "{0}.{1}",
    },
    "F_plain": {
        "description": "Plain numbered  (Section 14-32 or Section 14.32)",
        "pattern": re.compile(
            r'Section\s+(\d+)[-.](\d+[A-Za-z]?)[.\s]',
            re.IGNORECASE),
        "id_template": "{0}-{1}",
    },
}

NOISE_PATTERNS = [
    re.compile(r'^[A-Z ]{5,}\s+§\s*[\d.-]+\s*$'),
    re.compile(r'^§\s*[\d.-]+\s+[A-Z ]{5,}\s*$'),
    re.compile(r'^CD\d+:\d+[\d.]*$'),
    re.compile(r'^ZO\d+:\d+[\d.]*$'),
    re.compile(r'^Supp\.\s*No\.\s*\d+$', re.I),
    re.compile(r'^\d{1,4}$'),
    re.compile(r'^-\s*\d+\s*-$'),
]

CITATION_RE = re.compile(r'Ord(?:inance)?\.?\s*No\.?\s*[\d\w-]+', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Section:
    section_id: str
    section_name: str
    text: str
    page_start: int
    breadcrumb: str       # " > " joined outline path string
    citations: list[str]
    format_used: str


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def sample_pages(pdf_path: str, n_pages: int = 60) -> str:
    """Sample from three zones of the doc to skip front-matter."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        zones = [
            range(int(total * 0.10), min(int(total * 0.10) + n_pages // 3, total)),
            range(int(total * 0.45), min(int(total * 0.45) + n_pages // 3, total)),
            range(int(total * 0.75), min(int(total * 0.75) + n_pages // 3, total)),
        ]
        for zone in zones:
            for i in zone:
                text += (pdf.pages[i].extract_text() or "") + "\n"
    return text


def detect_format(sample_text: str, verbose: bool = True) -> Optional[str]:
    scores = Counter()
    for key, fmt in SECTION_FORMATS.items():
        scores[key] = len(fmt["pattern"].findall(sample_text))

    if verbose:
        print("\nFormat detection scores:")
        for key, count in scores.most_common():
            star = " <-- selected" if key == scores.most_common(1)[0][0] and count > 0 else ""
            print(f"  {key:<16} {SECTION_FORMATS[key]['description']:<52} {count} hits{star}")

    best = scores.most_common(1)
    return best[0][0] if best and best[0][1] > 0 else None


# ---------------------------------------------------------------------------
# Outline
# ---------------------------------------------------------------------------

def build_outline(pdf_path: str) -> list[dict]:
    reader = pypdf.PdfReader(pdf_path)
    flat = []
    _walk_outline(reader.outline or [], reader, flat, 0)
    return flat


def _walk_outline(items, reader, flat, depth):
    for item in items:
        if isinstance(item, list):
            _walk_outline(item, reader, flat, depth + 1)
        elif isinstance(item, dict):
            page_idx = 0
            page_ref = item.get("/Page")
            if page_ref is not None:
                try:
                    for pi, p in enumerate(reader.pages):
                        if (p.indirect_reference and
                                p.indirect_reference.idnum == page_ref.idnum):
                            page_idx = pi
                            break
                except Exception:
                    pass
            flat.append({
                "title": item.get("/Title", "").strip(),
                "page": page_idx,
                "depth": depth,
            })


def breadcrumb_at(page_idx: int, outline: list[dict]) -> str:
    """Return the deepest outline path string at or before page_idx."""
    path = []
    for entry in outline:
        if entry["page"] > page_idx:
            break
        depth = entry["depth"]
        path = path[:depth] + [entry["title"]]
    return " > ".join(path)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def clean_text(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(p.match(line) for p in NOISE_PATTERNS):
            continue
        lines.append(line)
    return " ".join(lines)


def split_sections(text: str, fmt_key: str, page_num: int) -> list[dict]:
    pattern = SECTION_FORMATS[fmt_key]["pattern"]
    tmpl = SECTION_FORMATS[fmt_key]["id_template"]
    matches = list(pattern.finditer(text))
    out = []
    for idx, m in enumerate(matches):
        sid = tmpl.format(*m.groups())
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        nm = re.match(r'^([^\n.]{3,120}[.\n])', body)
        name = nm.group(1).strip() if nm else ""
        if nm:
            body = body[nm.end():].strip()
        citations = list(set(CITATION_RE.findall(text[m.start():end])))
        out.append({"section_id": sid, "section_name": name,
                    "text": body, "page_start": page_num, "citations": citations})
    return out


def sort_key(s: Section):
    parts = re.split(r'[.\-]', s.section_id)
    return [(int(x), "") if x.isdigit() else (0, x) for x in parts]


# ---------------------------------------------------------------------------
# Output helpers — streaming (append) so chunks can be merged automatically
# ---------------------------------------------------------------------------

def load_existing_json(path: Path) -> dict:
    """Load existing JSON output as a dict keyed by section_id."""
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return {r["section_id"]: r for r in data}
        except Exception:
            pass
    return {}


def save_json(existing: dict, new_sections: list[Section], path: Path):
    for s in new_sections:
        d = asdict(s)
        sid = d["section_id"]
        if sid not in existing or len(d["text"]) > len(existing[sid].get("text", "")):
            existing[sid] = d
    ordered = sorted(existing.values(), key=lambda r: sort_key(
        Section(section_id=r["section_id"], section_name="", text=r.get("text",""),
                page_start=0, breadcrumb="", citations=[], format_used="")))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2, ensure_ascii=False)
    print(f"JSON  → {path}  ({len(ordered)} total sections)")


def save_csv(sections: list[Section], path: Path, append: bool = False):
    fields = ["section_id", "section_name", "page_start",
              "breadcrumb", "citations", "format_used", "text"]
    mode = "a" if append and path.exists() else "w"
    with open(path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if mode == "w":
            writer.writeheader()
        for s in sections:
            writer.writerow({
                "section_id": s.section_id,
                "section_name": s.section_name,
                "page_start": s.page_start,
                "breadcrumb": s.breadcrumb,
                "citations": "; ".join(s.citations),
                "format_used": s.format_used,
                "text": s.text[:1000],
            })
    total = sum(1 for _ in open(path, encoding="utf-8")) - 1
    print(f"CSV   → {path}  ({total} total rows)")


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

def scrape(
    pdf_path: str,
    county_name: Optional[str] = None,
    fmt_key: Optional[str] = None,
    page_range: Optional[tuple[int, int]] = None,
    verbose: bool = True,
) -> tuple[list[Section], str]:
    """
    Scrape sections from a municipal code PDF.

    page_range: (start, end) as 1-based page numbers, inclusive.
                None means all pages.
    Returns (sections, format_key).
    """
    pdf_path = str(pdf_path)
    if not county_name:
        county_name = Path(pdf_path).stem.replace("_", " ")

    if verbose:
        rng_str = f"  pages {page_range[0]}–{page_range[1]}" if page_range else "  all pages"
        print(f"\n{'='*60}")
        print(f"  {county_name}")
        print(f"  {pdf_path}")
        print(f" {rng_str}")
        print(f"{'='*60}")

    # Auto-detect format
    if not fmt_key:
        if verbose:
            print("\nAuto-detecting section format...")
        sample = sample_pages(pdf_path)
        fmt_key = detect_format(sample, verbose=verbose)
        if not fmt_key:
            print("\nERROR: Could not detect section format.")
            print("Re-run with --format A_irvine / B_dotted3 / C_simple2 / D_bare_dot3 / E_dotted2 / F_plain")
            return [], None
    elif verbose:
        print(f"\nFormat: {fmt_key} — {SECTION_FORMATS[fmt_key]['description']}")

    outline = build_outline(pdf_path)
    if verbose:
        print(f"Outline entries: {len(outline)}")

    seen: dict[str, Section] = {}
    CHUNK = 10

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        p_start = (page_range[0] - 1) if page_range else 0
        p_end   = min(page_range[1], total) if page_range else total

        if verbose:
            print(f"Processing pages {p_start+1}–{p_end} of {total} total\n")

        for chunk_start in range(p_start, p_end, CHUNK):
            chunk_end = min(chunk_start + CHUNK, p_end)
            chunk_text = ""
            for pi in range(chunk_start, chunk_end):
                chunk_text += "\n" + (pdf.pages[pi].extract_text() or "")

            chunk_text = clean_text(chunk_text)
            raw = split_sections(chunk_text, fmt_key, chunk_start + 1)

            for s in raw:
                sid = s["section_id"]
                crumb = breadcrumb_at(chunk_start, outline)
                sec = Section(
                    section_id=sid,
                    section_name=s["section_name"],
                    text=s["text"],
                    page_start=s["page_start"],
                    breadcrumb=crumb,
                    citations=s["citations"],
                    format_used=fmt_key,
                )
                if sid not in seen or len(s["text"]) > len(seen[sid].text):
                    seen[sid] = sec

            if verbose and raw:
                print(f"  Pages {chunk_start+1:>5}–{chunk_end:<5}  {len(raw):>4} sections")

    results = sorted(seen.values(), key=sort_key)
    if verbose:
        print(f"\nExtracted {len(results)} unique sections from this run.")
    return results, fmt_key


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_sections(sections: list[Section], query: str) -> list[Section]:
    q = query.lower()
    return [s for s in sections if
            q in s.text.lower() or q in s.section_name.lower() or q in s.breadcrumb.lower()]


def print_hits(hits: list[Section], query: str):
    print(f'\n{len(hits)} result(s) for "{query}":\n')
    for s in hits[:25]:
        print(f"  § {s.section_id}  {s.section_name}")
        if s.breadcrumb:
            print(f"    [{s.breadcrumb}]  p.{s.page_start}")
        idx = s.text.lower().find(query.lower())
        if idx >= 0:
            snip = s.text[max(0, idx-60): idx+200].replace("\n", " ")
            print(f"    …{snip}…")
        print()
    if len(hits) > 25:
        print(f"  (showing first 25 of {len(hits)} results)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_pages(s: str, total: int) -> tuple[int, int]:
    """Parse '100-500', '1-', '-500', or '100' into (start, end) 1-based."""
    s = s.strip()
    if '-' in s:
        parts = s.split('-', 1)
        start = int(parts[0]) if parts[0].strip() else 1
        end   = int(parts[1]) if parts[1].strip() else total
    else:
        start = end = int(s)
    return max(1, start), min(total, end)


def main():
    parser = argparse.ArgumentParser(
        description="Universal municipal code PDF scraper."
    )
    parser.add_argument("--pdf", required=True, help="Path to the PDF")
    parser.add_argument("--name", default=None, help="City/county name (for filenames)")
    parser.add_argument("--out", default="output", help="Output folder (default: output)")
    parser.add_argument("--format", default=None, dest="fmt",
                        choices=list(SECTION_FORMATS.keys()),
                        help="Force section format (skips auto-detect)")
    parser.add_argument("--formats", default="json,csv",
                        help="Output types: json,csv,txt  (default: json,csv)")
    parser.add_argument("--pages", default=None,
                        help="Page range to process, e.g. 1-500  or  501-  or  1-")
    parser.add_argument("--search", default=None,
                        help="Keyword to search after extraction")
    parser.add_argument("--detect-only", action="store_true",
                        help="Run format detection only, no extraction")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: file not found — {pdf_path}")
        sys.exit(1)

    # Detect-only
    if args.detect_only:
        print(f"Detecting format in {pdf_path.name} ...")
        detect_format(sample_pages(str(pdf_path)), verbose=True)
        return

    # Parse page range
    page_range = None
    if args.pages:
        with pdfplumber.open(str(pdf_path)) as pdf:
            total = len(pdf.pages)
        page_range = parse_pages(args.pages, total)
        print(f"Page range: {page_range[0]}–{page_range[1]}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    sections, fmt_used = scrape(
        pdf_path=str(pdf_path),
        county_name=args.name,
        fmt_key=args.fmt,
        page_range=page_range,
        verbose=not args.quiet,
    )

    if not sections:
        print("\nNo sections found. Try --detect-only to check the format,")
        print("then re-run with --format <key>.")
        sys.exit(1)

    stem = re.sub(r'[^\w]', '_', (args.name or pdf_path.stem).lower()).strip('_')
    fmts = [f.strip().lower() for f in args.formats.split(",")]
    appending = page_range is not None  # merge with previous chunk output

    if "json" in fmts:
        existing = load_existing_json(out_dir / f"{stem}.json")
        save_json(existing, sections, out_dir / f"{stem}.json")

    if "csv" in fmts:
        save_csv(sections, out_dir / f"{stem}.csv", append=appending)

    if "txt" in fmts:
        txt_path = out_dir / f"{stem}.txt"
        mode = "a" if appending and txt_path.exists() else "w"
        with open(txt_path, mode, encoding="utf-8") as f:
            for s in sections:
                f.write(f"{'='*70}\n§ {s.section_id}  —  {s.section_name}\n")
                if s.breadcrumb:
                    f.write(f"[{s.breadcrumb}]  p.{s.page_start}\n")
                f.write(f"\n{s.text}\n\n")
                if s.citations:
                    f.write(f"Citations: {', '.join(s.citations)}\n")
        print(f"TXT   → {txt_path}")

    # Search
    if args.search:
        hits = search_sections(sections, args.search)
        print_hits(hits, args.search)
        if hits:
            qstem = re.sub(r'[^\w]', '_', args.search.lower())
            save_json({}, hits, out_dir / f"{stem}_search_{qstem}.json")


if __name__ == "__main__":
    main()