"""
Fetch targeted federal regulations from the eCFR API (keyless) and write them
in the same enriched JSON shape that ingest.py consumes, tagged level=federal.

eCFR API: https://www.ecfr.gov/developers/documentation/api/v1  (no key needed)

Output: data_enriched/federal_<title>_<part>.json
Then run:  python ingest.py     (federal sections become searchable everywhere,
                                  because the retrieval filter always includes
                                  level=federal regardless of the user's city)

Usage:
    python fetch_federal.py                 # fetch the curated set below
    python fetch_federal.py --list          # show what would be fetched
"""
from __future__ import annotations
import argparse
import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from xml.etree import ElementTree as ET

API = "https://www.ecfr.gov/api/versioner/v1"
UA = {"User-Agent": "lexlocator-federal-fetcher"}
OUT_DIR = Path("data_enriched")

# Curated, relevant federal regulations per topic. Each entry fetches either a
# whole part or a single section. Add more as your topics grow.
FEDERAL_SOURCES = [
    # Drones / UAS
    {"title": 14, "part": "107", "topic": "drones",
     "source_title": "14 CFR Part 107 — Small Unmanned Aircraft Systems"},
    {"title": 14, "part": "89", "topic": "drones",
     "source_title": "14 CFR Part 89 — Remote Identification of UAS"},
    {"title": 14, "part": "48", "topic": "drones",
     "source_title": "14 CFR Part 48 — Registration of Small UAS"},

    # E-bikes / bicycles (federal product rules)
    {"title": 16, "part": "1512", "topic": "ebikes",
     "source_title": "16 CFR Part 1512 — Requirements for Bicycles"},

    # Service animals (relevant to dog/leash questions)
    {"title": 28, "section": "36.302", "topic": "service_animals",
     "source_title": "28 CFR 36.302 — Service animals (public accommodations)"},
    {"title": 28, "section": "35.136", "topic": "service_animals",
     "source_title": "28 CFR 35.136 — Service animals (state/local government)"},
]

SEC_SYMBOL = "§"


def http_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def http_text(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", "ignore")


def latest_dates() -> dict:
    """Map title number -> latest issue date (YYYY-MM-DD)."""
    data = http_json(f"{API}/titles.json")
    return {t["number"]: t.get("latest_issue_date") for t in data["titles"]}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def parse_sections(xml_text: str, source_title: str, title_name: str,
                   topic: str) -> list[dict]:
    """Extract every DIV8 SECTION from an eCFR XML payload."""
    out = []
    root = ET.fromstring(xml_text.encode("utf-8"))
    # The payload may itself be a DIV8 (single section) or contain many.
    div8s = ([root] if root.tag == "DIV8" and root.get("TYPE") == "SECTION"
             else root.findall(".//DIV8[@TYPE='SECTION']"))
    for div in div8s:
        n = div.get("N", "")
        meta_raw = div.get("hierarchy_metadata", "")
        citation, path = "", ""
        if meta_raw:
            try:
                meta = json.loads(meta_raw)
                citation = meta.get("citation", "")
                path = meta.get("path", "")
            except ValueError:
                pass
        section_id = citation or f"{n}"

        head = div.find("HEAD")
        head_txt = clean("".join(head.itertext())) if head is not None else ""
        # strip leading "§ 107.1 " -> keep just the name
        name = re.sub(rf"^{SEC_SYMBOL}?\s*[\d.\-]+\s*", "", head_txt).strip()

        # body = all paragraph-like text, excluding the HEAD
        parts = []
        for el in div.iter():
            if el.tag in ("P", "FP", "FP-1", "FP-2"):
                parts.append(clean("".join(el.itertext())))
        body = clean(" ".join(p for p in parts if p))
        if len(body) < 20:
            continue

        # citations: CITA / amendment notes
        cites = [clean("".join(c.itertext())) for c in div.findall(".//CITA")]
        cites = [c for c in cites if c]

        # build a clean public URL from the path
        url = ""
        if path:
            url = "https://www.ecfr.gov/current" + path.replace("/on/_SUBSTITUTE_DATE_", "")
        if not url:
            url = "https://www.ecfr.gov"

        out.append({
            "section_id": section_id,
            "section_name": name,
            "text": body,
            "page_start": 0,
            "breadcrumb": f"{title_name} > {source_title}",
            "citations": cites,
            "topic": topic,
            "jurisdiction": {
                "level": "federal",
                "city": "",
                "county": "",
                "state": "",
                "country": "US",
                "source_title": source_title,
                "source_url": url,
            },
            "source_file": "federal",
        })
    return out


def fetch_one(src: dict, date: str) -> list[dict]:
    title = src["title"]
    if "section" in src:
        url = f"{API}/full/{date}/title-{title}.xml?section={src['section']}"
    else:
        url = f"{API}/full/{date}/title-{title}.xml?part={src['part']}"
    xml = http_text(url)
    return parse_sections(xml, src["source_title"], f"Title {title}", src["topic"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="Show sources and exit")
    args = ap.parse_args()

    if args.list:
        for s in FEDERAL_SOURCES:
            tgt = s.get("part") and f"part {s['part']}" or f"section {s['section']}"
            print(f"  Title {s['title']} {tgt:<14} [{s['topic']}]  {s['source_title']}")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Fetching latest issue dates...")
    dates = latest_dates()

    grand_total = 0
    for src in FEDERAL_SOURCES:
        title = src["title"]
        date = dates.get(title)
        tgt = src.get("part") and f"part-{src['part']}" or f"sec-{src['section']}"
        if not date:
            print(f"  SKIP Title {title} — no date available")
            continue
        try:
            sections = fetch_one(src, date)
        except urllib.error.HTTPError as e:
            print(f"  ERROR Title {title} {tgt}: HTTP {e.code}")
            continue
        except Exception as e:
            print(f"  ERROR Title {title} {tgt}: {e}")
            continue

        out_path = OUT_DIR / f"federal_{title}_{tgt}.json"
        out_path.write_text(json.dumps(sections, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        grand_total += len(sections)
        print(f"  Title {title} {tgt:<12} -> {out_path.name}  ({len(sections)} sections)  [{date}]")
        time.sleep(0.5)  # be polite to the API

    print(f"\nDone. {grand_total} federal sections written to {OUT_DIR}/.")
    print("Next:  python ingest.py     (then they're searchable for every location)")


if __name__ == "__main__":
    main()
