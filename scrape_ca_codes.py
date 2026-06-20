"""
Scrape ALL California codes + the State Constitution from leginfo and write them
in the enriched JSON shape ingest.py consumes, tagged level=state (state=CA).

Site: https://leginfo.legislature.ca.gov/faces/codes.xhtml

How it works (the site is a JSF tree):
  codes.xhtml ........... lists the 29 codes + Constitution (tocCode)
  codesTOCSelected ...... per-code: top-level branch links (expandedbranch)
  expandedbranch ........ intermediate nodes: more branch links, sometimes sections
  displayText ........... leaf nodes: the actual section text
Sections appear as:  <h6><a ... submitCodesValues('312.5.', ...)>312.5.</a></h6> <text>
The 'nodetreepath' index is stateful, so we only ever follow links found on a
page — never construct them. We crawl every branch/leaf within a code, parse
sections wherever they appear, and dedupe by section number.

This is a BIG scrape (the full CA codes are ~250k sections). It is:
  - per-code  (run a subset with --codes VEH,PEN,CIV)
  - resumable (skips codes whose output file already exists; --force to redo)
  - polite    (--delay seconds between requests, default 0.4)

Usage:
  python scrape_ca_codes.py --codes VEH,PEN,CIV,HSC      # recommended: key codes
  python scrape_ca_codes.py                              # ALL codes + Constitution
  python scrape_ca_codes.py --codes VEH --delay 0.6
Then:
  python ingest.py
"""
from __future__ import annotations
import argparse
import json
import re
import time
import html as H
import urllib.request
import urllib.error
from collections import deque
from pathlib import Path

BASE = "https://leginfo.legislature.ca.gov/faces/"
OUT_DIR = Path("data_enriched")
UA = {"User-Agent": "Mozilla/5.0 (compatible; lexlocator-research)"}

CODE_NAMES = {
    "BPC": "Business and Professions Code", "CIV": "Civil Code",
    "CCP": "Code of Civil Procedure", "COM": "Commercial Code",
    "CORP": "Corporations Code", "EDC": "Education Code", "ELEC": "Elections Code",
    "EVID": "Evidence Code", "FAM": "Family Code", "FIN": "Financial Code",
    "FGC": "Fish and Game Code", "FAC": "Food and Agricultural Code",
    "GOV": "Government Code", "HNC": "Harbors and Navigation Code",
    "HSC": "Health and Safety Code", "INS": "Insurance Code", "LAB": "Labor Code",
    "MVC": "Military and Veterans Code", "PEN": "Penal Code", "PROB": "Probate Code",
    "PCC": "Public Contract Code", "PRC": "Public Resources Code",
    "PUC": "Public Utilities Code", "RTC": "Revenue and Taxation Code",
    "SHC": "Streets and Highways Code", "UIC": "Unemployment Insurance Code",
    "VEH": "Vehicle Code", "WAT": "Water Code",
    "WIC": "Welfare and Institutions Code", "CONS": "California Constitution",
}

# Section delimiter: an <h6> whose <a> calls submitCodesValues('<num>.', ...)
SEC_RE = re.compile(
    r"<h6[^>]*>\s*<a[^>]*submitCodesValues\('([^']+?)'[^>]*>.*?</a>\s*</h6>",
    re.I | re.S,
)
HISTORY_RE = re.compile(r"\((?:Added|Amended|Repealed|Enacted|Renumbered)[^)]*\)", re.S)
DISPLAY_LINK_RE = re.compile(
    r"codes_display(?:Text|expandedbranch)\.xhtml\?[^\"'> ]+", re.I)


def get(url: str, delay: float) -> str:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                charset = r.headers.get_content_charset() or "utf-8"
                html = r.read().decode(charset, "ignore")
            time.sleep(delay)
            return html
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 2:
                print(f"      ! failed {url[:80]}: {e}")
                return ""
            time.sleep(2 * (attempt + 1))
    return ""


def strip_tags(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = H.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_params(url: str) -> dict:
    q = url.split("?", 1)[1] if "?" in url else ""
    out = {}
    for kv in q.split("&"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            out[k] = H.unescape(v)
    return out


def breadcrumb(code: str, params: dict) -> str:
    parts = [CODE_NAMES.get(code, code)]
    for key, label in [("division", "Div"), ("title", "Title"), ("part", "Part"),
                       ("chapter", "Ch"), ("article", "Art")]:
        v = params.get(key, "").strip().rstrip(".")
        if v:
            parts.append(f"{label} {v}")
    return " > ".join(parts)


def parse_sections(html: str, code: str, params: dict) -> dict:
    """Return {section_num: record} for every section delimited on this page."""
    out = {}
    matches = list(SEC_RE.finditer(html))
    crumb = breadcrumb(code, params)
    src_url = (BASE + "codes_displaySection.xhtml?lawCode=" + code + "&sectionNum=")
    for i, m in enumerate(matches):
        num = m.group(1).strip().rstrip(".")
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        body_html = html[start:end]
        text = strip_tags(body_html)
        if len(text) < 15:
            continue
        hist = HISTORY_RE.findall(text)
        citation = hist[-1] if hist else ""
        out[num] = {
            "section_id": f"CA {code} § {num}",
            "section_name": "",
            "text": text,
            "page_start": 0,
            "breadcrumb": crumb,
            "citations": [citation] if citation else [],
            "jurisdiction": {
                "level": "state", "city": "", "county": "", "state": "CA",
                "country": "US",
                "source_title": f"California {CODE_NAMES.get(code, code)}",
                "source_url": src_url + num + ".",
            },
            "source_file": f"state_ca_{code.lower()}",
        }
    return out


def crawl_code(code: str, delay: float, max_pages: int) -> list[dict]:
    toc = get(BASE + f"codesTOCSelected.xhtml?tocCode={code}", delay)
    seeds = [H.unescape(u) for u in DISPLAY_LINK_RE.findall(toc)]
    queue = deque(BASE + u for u in seeds)
    visited = set()
    sections: dict[str, dict] = {}
    pages = 0

    while queue and pages < max_pages:
        url = queue.popleft()
        norm = url.split("nodetreepath=")[0]  # dedupe ignoring volatile index tail
        key = (url.split("?", 1)[1] if "?" in url else url)
        if key in visited:
            continue
        visited.add(key)
        html = get(url, delay)
        if not html:
            continue
        pages += 1

        params = parse_params(url)
        found = parse_sections(html, code, params)
        for num, rec in found.items():
            if num not in sections or len(rec["text"]) > len(sections[num]["text"]):
                sections[num] = rec

        # enqueue child branch/leaf links that belong to THIS code
        for link in DISPLAY_LINK_RE.findall(html):
            link = H.unescape(link)
            if f"Code={code}" not in link and f"tocCode={code}" not in link \
                    and f"lawCode={code}" not in link:
                continue
            child = BASE + link
            ckey = child.split("?", 1)[1]
            if ckey not in visited:
                queue.append(child)

        if pages % 25 == 0:
            print(f"    {code}: {pages} pages, {len(sections)} sections so far...")

    return list(sections.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default="ALL",
                    help="Comma list (e.g. VEH,PEN,CIV) or ALL")
    ap.add_argument("--delay", type=float, default=0.4, help="Seconds between requests")
    ap.add_argument("--max-pages", type=int, default=100000, help="Safety cap per code")
    ap.add_argument("--force", action="store_true", help="Re-scrape even if output exists")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    codes = (list(CODE_NAMES) if args.codes.upper() == "ALL"
             else [c.strip().upper() for c in args.codes.split(",")])

    grand = 0
    for code in codes:
        if code not in CODE_NAMES:
            print(f"Skip unknown code {code}")
            continue
        out_path = OUT_DIR / f"state_ca_{code.lower()}.json"
        if out_path.exists() and not args.force:
            print(f"= {code}: exists, skipping (use --force to redo)")
            continue
        print(f"\n>> {code}  ({CODE_NAMES[code]})")
        t0 = time.time()
        recs = crawl_code(code, args.delay, args.max_pages)
        out_path.write_text(json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")
        grand += len(recs)
        print(f"   {code}: {len(recs)} sections -> {out_path.name}  ({time.time()-t0:.0f}s)")

    print(f"\nDone. {grand} CA state sections written to {OUT_DIR}/.")
    print("Next:  python ingest.py")


if __name__ == "__main__":
    main()
