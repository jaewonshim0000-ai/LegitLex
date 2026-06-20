"""
Scrape Korean statutes from the OFFICIAL 국가법령정보센터 (law.go.kr) Open API
into the enriched JSON shape ingest.py consumes, tagged level=national,
country=KR. Authoritative + current (supersedes the Wikisource fallback).

API (DRF):
  search : https://www.law.go.kr/DRF/lawSearch.do?OC=<oc>&target=law&type=JSON&query=<name>
  content: https://www.law.go.kr/DRF/lawService.do?OC=<oc>&target=law&type=JSON&MST=<mst>

OC = the ID part (before @) of the email you registered at open.law.go.kr.
Put it in .env as KR_LAW_OC=...

Usage:
  python scrape_kr_lawgo.py
  python scrape_kr_lawgo.py --laws "도로교통법,형법"
  python scrape_kr_lawgo.py --oc myid
Then:
  python ingest.py   (after the app's retrieval is made country-aware)
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from lexlocator import config  # noqa: F401  (loads .env -> KR_LAW_OC)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SEARCH = "https://www.law.go.kr/DRF/lawSearch.do"
SERVICE = "https://www.law.go.kr/DRF/lawService.do"
OUT_DIR = Path("data_enriched")
HDRS = {"User-Agent": "Mozilla/5.0 lexlocator-kr"}

# Curated everyday-compliance Korean statutes (Korean name, slug, English, topic)
KR_LAWS = [
    ("도로교통법", "kr_road_traffic", "Road Traffic Act", "traffic"),
    ("형법", "kr_criminal", "Criminal Act", "criminal"),
    ("경범죄 처벌법", "kr_minor_offenses", "Minor Offenses Act", "public_order"),
    ("동물보호법", "kr_animal_protection", "Animal Protection Act", "animals"),
    ("국민건강증진법", "kr_health_promotion", "National Health Promotion Act", "health"),
    ("폐기물관리법", "kr_waste", "Wastes Control Act", "waste"),
    ("청소년 보호법", "kr_youth_protection", "Juvenile Protection Act", "youth"),
]


def oc() -> str:
    o = os.environ.get("KR_LAW_OC", "").strip()
    if not o:
        raise SystemExit("KR_LAW_OC not set. Add it to .env (your law.go.kr OC).")
    return o


def http_json(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=60) as r:
        raw = r.read().decode("utf-8", "ignore")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # API returns an error message as plain text/HTML when auth fails
        raise RuntimeError("Non-JSON response (check OC / API access): " + raw[:160])


def as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def clean(s: str) -> str:
    if not isinstance(s, str):
        s = str(s or "")
    s = s.replace("<br/>", "\n").replace("<br>", "\n")
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
           .replace("&nbsp;", " ").replace("&#13;", " "))
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def find_mst(name: str, key: str) -> tuple[str, str] | None:
    """Return (MST, official_name) for the CURRENT version of a law by name."""
    q = urllib.parse.urlencode({"OC": key, "target": "law", "type": "JSON",
                                "query": name, "display": "20"})
    data = http_json(f"{SEARCH}?{q}")
    laws = as_list(((data or {}).get("LawSearch") or {}).get("law"))
    # exact-name current law first, else first current, else first
    def nm(l): return (l.get("법령명한글") or "").strip()
    def cur(l): return "현행" in (l.get("현행연혁코드") or l.get("현행연혁") or "현행")
    exact = [l for l in laws if nm(l) == name]
    pool = exact or laws
    cands = [l for l in pool if cur(l)] or pool
    if not cands:
        return None
    l = cands[0]
    mst = l.get("법령일련번호") or l.get("법령MST") or l.get("MST")
    return (str(mst), nm(l)) if mst else None


def fetch_articles(mst: str, key: str):
    q = urllib.parse.urlencode({"OC": key, "target": "law", "type": "JSON", "MST": mst})
    data = http_json(f"{SERVICE}?{q}")
    root = data.get("법령") or data
    basic = root.get("기본정보", {}) if isinstance(root, dict) else {}
    units = as_list(((root or {}).get("조문") or {}).get("조문단위"))
    return basic, units


def article_text(unit: dict) -> str:
    """Assemble the full article text.

    Single-paragraph articles inline the whole body in 조문내용 (e.g.
    '제1조(목적) 이 법은 ...'). Multi-paragraph articles put ONLY the heading in
    조문내용 ('제1조(범죄의 성립과 처벌)') and the actual provisions in the 항
    array (each 항내용 already carries its ①②③ marker), with 호 nested under 항.
    So: start from 조문내용 (heading or full body), then always append any 항/호.
    """
    head = clean(unit.get("조문내용") or "")
    hangs = as_list(unit.get("항"))
    hos = as_list(unit.get("호"))   # some articles carry 호 directly (no 항)
    if not hangs and not hos:
        return head

    parts = [head] if head else []
    for hang in hangs:
        h = clean(hang.get("항내용") or "")
        if h:
            parts.append(h)
        for ho in as_list(hang.get("호")):
            ho_t = clean(ho.get("호내용") or "")
            if ho_t:
                parts.append("  " + ho_t)
    for ho in hos:
        ho_t = clean(ho.get("호내용") or "")
        if ho_t:
            parts.append("  " + ho_t)
    return "\n".join(parts).strip()


def year_of(*vals) -> str:
    for v in vals:
        m = re.search(r"(19|20)\d{2}", str(v or ""))
        if m:
            return m.group(0)
    return ""


def scrape_law(name: str, slug: str, english: str, topic: str, key: str) -> list[dict]:
    found = find_mst(name, key)
    if not found:
        print(f"  ! {name}: not found via search")
        return []
    mst, official = found
    basic, units = fetch_articles(mst, key)
    law_no = basic.get("공포번호") or ""
    yr = year_of(basic.get("공포일자"), basic.get("시행일자"))
    law_id = basic.get("법령ID") or ""
    url = (f"https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq={mst}"
           if mst else "https://www.law.go.kr")

    out, seen = [], set()
    for u in units:
        if not isinstance(u, dict):
            continue
        if (u.get("조문여부") or "조문") != "조문":
            continue  # skip 장/절 headers (전문)
        num = str(u.get("조문번호") or "").strip()
        if not num or not num[0].isdigit():
            continue
        ga = str(u.get("조문가지번호") or "").strip()
        jo = f"제{num}조" + (f"의{ga}" if ga and ga != "0" else "")
        if jo in seen:
            continue
        seen.add(jo)
        body = article_text(u)
        if len(body) < 8:
            continue
        out.append({
            "section_id": jo,
            "section_name": clean(u.get("조문제목") or ""),
            "text": body,
            "page_start": 0,
            "breadcrumb": f"{official} ({english})",
            "citations": [f"{official} {jo}" + (f" (제{law_no}호)" if law_no else "")],
            "topic": topic,
            "jurisdiction": {
                "level": "national", "city": "", "county": "", "state": "",
                "country": "KR",
                "source_title": f"{official} ({english})",
                "source_url": url,
            },
            "last_amended": yr,
            "source_file": slug,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--laws", default="", help="Comma-separated Korean law names (default: curated set)")
    ap.add_argument("--oc", default="", help="Override KR_LAW_OC")
    args = ap.parse_args()
    if args.oc.strip():
        os.environ["KR_LAW_OC"] = args.oc.strip()
    key = oc()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.laws.strip():
        wanted = [(n.strip(), "kr_" + re.sub(r"\W+", "", n)[:14], n.strip(), "custom")
                  for n in args.laws.split(",") if n.strip()]
    else:
        wanted = KR_LAWS

    grand = 0
    for name, slug, english, topic in wanted:
        try:
            recs = scrape_law(name, slug, english, topic, key)
        except Exception as e:
            print(f"  ERROR {name}: {e}")
            continue
        if not recs:
            continue
        (OUT_DIR / f"{slug}.json").write_text(
            json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")
        grand += len(recs)
        print(f"  {name} ({english}): {len(recs)} articles -> {slug}.json")
        time.sleep(0.5)

    print(f"\nDone. {grand} Korean statute articles written to {OUT_DIR}/.")


if __name__ == "__main__":
    main()
