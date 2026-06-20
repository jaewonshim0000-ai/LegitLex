"""
Enrich scraped JSON with jurisdiction metadata.

Reads every *.json file in data/ and writes a parallel file to data_enriched/
with each section tagged with city / county / state / level info from
jurisdictions.json. The vector DB uses these tags to filter results by the
user's GPS-derived location.

Usage:
    python enrich.py
    python enrich.py --data-dir data --out-dir data_enriched
"""
from __future__ import annotations
import json
import re
import argparse
from pathlib import Path


def clean_text(s: str) -> str:
    """The scraper sometimes glues words together when PDFs lack spaces.
    This is a light cleanup that helps embeddings find the right matches
    without losing the original meaning."""
    if not s:
        return s
    # Insert space between a lowercase->uppercase boundary inside a token
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', s)
    # Insert space between a letter and a digit run
    s = re.sub(r'([A-Za-z])(\d)', r'\1 \2', s)
    s = re.sub(r'(\d)([A-Za-z])', r'\1 \2', s)
    # Collapse repeated whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def enrich_file(src: Path, jurisdiction: dict, out: Path) -> int:
    data = json.loads(src.read_text(encoding='utf-8'))
    enriched = []
    for row in data:
        text = clean_text(row.get('text', ''))
        if len(text) < 30:
            # Skip near-empty sections (just headers, page numbers, etc.)
            continue
        enriched.append({
            **row,
            'text': text,
            'section_name': clean_text(row.get('section_name', '')),
            'breadcrumb': row.get('breadcrumb', ''),
            'jurisdiction': jurisdiction,
            'source_file': src.stem,
        })
    out.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding='utf-8')
    return len(enriched)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    ap.add_argument('--out-dir', default='data_enriched')
    ap.add_argument('--config', default='jurisdictions.json')
    args = ap.parse_args()

    config = json.loads(Path(args.config).read_text(encoding='utf-8'))
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for src in sorted(data_dir.glob('*.json')):
        key = src.stem
        if key not in config:
            print(f'  SKIP {src.name} — no entry in {args.config}')
            continue
        jurisdiction = {k: v for k, v in config[key].items() if not k.startswith('_')}
        out = out_dir / src.name
        n = enrich_file(src, jurisdiction, out)
        total += n
        print(f'  {src.name:35s} -> {out}  ({n} sections, {jurisdiction["level"]}: {jurisdiction.get("city") or jurisdiction.get("county") or jurisdiction.get("state")})')

    print(f'\nDone. {total} sections enriched.')


if __name__ == '__main__':
    main()
