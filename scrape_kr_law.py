"""
Scrape Korean statutes (대한민국 법령) into the enriched JSON shape ingest.py
consumes, tagged level=national, country=KR.

SOURCE: Korean Wikisource (ko.wikisource.org) — public-domain full statute text,
keyless MediaWiki API. (The official 국가법령정보센터 / law.go.kr Open API is more
authoritative + current, but requires free OC registration + IP allow-listing;
see notes at the bottom.)

Each statute's wikitext looks like:
    {{대한민국 법령 |제목=경범죄 처벌법 |호수=13813 |시행일자=2016.7.23 ...}}
    === 제1장 총칙 ===
    * '''<span id='1'>제1조(목적)</span>''' 이 법은 ...
We parse the metadata, then split into 제N조 articles (with their chapter as the
breadcrumb) and clean the wiki markup.

Usage:
    python scrape_kr_law.py
    python scrape_kr_law.py --laws "경범죄 처벌법,동물보호법"
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

API = "https://ko.wikisource.org/w/api.php"
OUT_DIR = Path("data_enriched")
HDRS = {"User-Agent": "lexlocator-kr/1.0 (legal research)"}

# Curated everyday-compliance Korean statutes available with full text.
# (title, output-slug, english name, topic)
KR_LAWS = [
    ("경범죄 처벌법", "kr_minor_offenses", "Minor Offenses Act", "public_order"),
    ("동물보호법", "kr_animal_protection", "Animal Protection Act", "animals"),
    ("집회 및 시위에 관한 법률", "kr_assembly", "Assembly and Demonstration Act", "assembly"),
    ("국민건강증진법", "kr_health_promotion", "National Health Promotion Act", "health"),
]

ART_SPAN = re.compile(r"<span id='[^']*'>\s*(제\d+조(?:의\d+)?)\s*(\([^)]*\))?\s*</span>")
ART_BOLD = re.compile(r"'''\s*(제\d+조(?:의\d+)?)\s*(\([^)]*\))?\s*'''")
CHAPTER = re.compile(r"^=+\s*(제\d+장[^=]*?)\s*=+\s*$", re.M)


def fetch_wikitext(title: str) -> str | None:
    params = {"action": "query", "prop": "revisions", "rvprop": "content",
              "rvslots": "main", "format": "json", "titles": title, "redirects": 1}
    url = API + "?" + urllib.parse.urlencode(params)
    d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=60))
    for _, p in d["query"]["pages"].items():
        if "revisions" in p:
            return p["revisions"][0]["slots"]["main"]["*"]
    return None


def meta(field: str, text: str) -> str:
    m = re.search(r"\|\s*" + field + r"\s*=\s*([^\n|}]+)", text)
    return m.group(1).strip() if m else ""


def clean(s: str) -> str:
    s = re.sub(r"\{\{[^}]*\}\}", " ", s)            # templates
    s = re.sub(r"<span[^>]*>|</span>", "", s)        # spans
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)  # [[a|b]] -> b
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)        # [[a]] -> a
    s = s.replace("'''", "").replace("''", "")
    s = re.sub(r"<[^>]+>", "", s)                    # other tags
    s = re.sub(r"(?m)^[\*:;#]+\s*", " ", s)          # list markers
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def chapter_at(pos: int, chapters: list[tuple[int, str]]) -> str:
    cur = ""
    for cpos, name in chapters:
        if cpos <= pos:
            cur = name
        else:
            break
    return cur


def parse_law(title: str, slug: str, english: str, topic: str) -> list[dict]:
    wt = fetch_wikitext(title)
    if not wt:
        print(f"  ! {title}: not found")
        return []
    law_no = meta("호수", wt)
    eff = meta("시행일자", wt)            # e.g. 2016.7.23
    amend = meta("제정개정일자", wt) or eff
    ym = re.search(r"(19|20)\d{2}", amend)
    year = ym.group(0) if ym else ""

    chapters = [(m.start(), clean(m.group(1))) for m in CHAPTER.finditer(wt)]

    arts = list(ART_SPAN.finditer(wt))
    if len(arts) < 5:
        arts = list(ART_BOLD.finditer(wt))
    src_url = "https://ko.wikisource.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))

    out = []
    seen = set()
    for i, m in enumerate(arts):
        jo = m.group(1)                  # 제N조
        name = (m.group(2) or "").strip("()")
        if jo in seen:
            continue
        seen.add(jo)
        start = m.end()
        end = arts[i + 1].start() if i + 1 < len(arts) else len(wt)
        body = clean(wt[start:end])
        if len(body) < 10:
            continue
        crumb = f"{title} ({english})"
        ch = chapter_at(m.start(), chapters)
        if ch:
            crumb += " > " + ch
        out.append({
            "section_id": jo,
            "section_name": name,
            "text": body,
            "page_start": 0,
            "breadcrumb": crumb,
            "citations": [f"{title} {jo}" + (f" (법률 제{law_no}호)" if law_no else "")],
            "topic": topic,
            "jurisdiction": {
                "level": "national",
                "city": "", "county": "", "state": "",
                "country": "KR",
                "source_title": f"{title} ({english})",
                "source_url": src_url,
            },
            "last_amended": year,
            "source_file": slug,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--laws", default="", help="Comma-separated Korean law titles (default: curated set)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.laws.strip():
        wanted = [(t.strip(), "kr_" + re.sub(r"\W+", "", t)[:14], t.strip(), "custom")
                  for t in args.laws.split(",") if t.strip()]
    else:
        wanted = KR_LAWS

    grand = 0
    for title, slug, english, topic in wanted:
        recs = parse_law(title, slug, english, topic)
        if not recs:
            continue
        out_path = OUT_DIR / f"{slug}.json"
        out_path.write_text(json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")
        grand += len(recs)
        print(f"  {title} ({english}): {len(recs)} articles -> {out_path.name}")

    print(f"\nDone. {grand} Korean statute articles written to {OUT_DIR}/.")


if __name__ == "__main__":
    main()
