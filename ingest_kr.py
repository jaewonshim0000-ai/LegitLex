"""
Ingest Korean statutes into a SEPARATE ChromaDB collection (`laws_kr`) embedded
with a MULTILINGUAL model, because the English `all-MiniLM-L6-v2` used for the US
`laws` collection cannot embed Korean meaningfully (retrieval would be random).

This keeps the two worlds isolated: US queries hit `laws` (English model), KR
queries hit `laws_kr` (multilingual model). See lexlocator/core.retrieve.

Picks up every data_enriched/*.json section whose jurisdiction.country == 'KR'
(covers kr_*.json). Reuses the same chunking/document shape as ingest.py.

Usage:
    python ingest_kr.py            # build/refresh laws_kr (upsert)
    python ingest_kr.py --reset    # wipe laws_kr first
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from ingest import chunk_section   # reuse identical clause-aware chunking

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

KR_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
KR_COLLECTION = "laws_kr"


def ingest(data_dir: Path, db_path: Path, reset: bool):
    client = chromadb.PersistentClient(
        path=str(db_path),
        settings=Settings(anonymized_telemetry=False),
    )

    if reset:
        try:
            client.delete_collection(KR_COLLECTION)
            print(f"Reset collection: {KR_COLLECTION}")
        except Exception:
            pass

    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=KR_MODEL
    )
    collection = client.get_or_create_collection(
        name=KR_COLLECTION,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    json_files = sorted(data_dir.glob("*.json"))
    BATCH = 128
    ids, docs, metas = [], [], []
    total, seen = 0, set()

    for src in json_files:
        sections = json.loads(src.read_text(encoding="utf-8"))
        kr = [s for s in sections
              if (s.get("jurisdiction", {}).get("country", "") or "").upper() == "KR"]
        if not kr:
            continue
        print(f"  {src.name}: {len(kr)} KR sections")
        for sec in kr:
            for i, chunk in enumerate(chunk_section(sec)):
                j = sec.get("jurisdiction", {})
                meta = {
                    "section_id": sec.get("section_id", ""),
                    "section_name": sec.get("section_name", ""),
                    "breadcrumb": sec.get("breadcrumb", ""),
                    "page_start": int(sec.get("page_start", 0) or 0),
                    "source_file": sec.get("source_file", src.stem),
                    "source_title": j.get("source_title", ""),
                    "source_url": j.get("source_url", ""),
                    "level": j.get("level", "national"),
                    "city": j.get("city", ""),
                    "county": j.get("county", ""),
                    "state": j.get("state", ""),
                    "country": "KR",
                    "chunk_index": i,
                }
                doc_id = f'{sec.get("source_file", src.stem)}::{sec.get("section_id", "?")}::{i}'
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                ids.append(doc_id); docs.append(chunk); metas.append(meta)
                if len(ids) >= BATCH:
                    collection.upsert(ids=ids, documents=docs, metadatas=metas)
                    total += len(ids); ids, docs, metas = [], [], []

    if ids:
        collection.upsert(ids=ids, documents=docs, metadatas=metas)
        total += len(ids)

    print(f"\nIngested {total} Korean chunks.")
    print(f'Collection "{KR_COLLECTION}" now holds {collection.count()} chunks at {db_path}.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data_enriched")
    ap.add_argument("--db", default="vectordb")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    ingest(Path(args.data_dir), Path(args.db), args.reset)


if __name__ == "__main__":
    main()
