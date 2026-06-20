"""
Ingest enriched JSON into a local ChromaDB collection.

Each section becomes one document (or several chunks if very long). Metadata
holds the jurisdiction tags so retrieval can filter by city/county/state.

Usage:
    python ingest.py
    python ingest.py --reset           # wipe the collection and re-ingest
    python ingest.py --collection laws --db ./vectordb
"""
from __future__ import annotations
import json
import argparse
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions


CHUNK_CHAR_LIMIT = 1000   # smaller window => each clause/paragraph stays focused,
CHUNK_OVERLAP = 150       # so a single buried subsection still ranks well.


def _split_long_line(line: str, limit: int) -> list[str]:
    """A single line longer than the limit: fall back to sentence-ish windows."""
    out, start = [], 0
    while start < len(line):
        end = min(start + limit, len(line))
        if end < len(line):
            dot = line.rfind('. ', start, end)
            if dot > start + limit // 2:
                end = dot + 1
        out.append(line[start:end].strip())
        start = end
    return [c for c in out if c]


def chunk_body(text: str, limit: int = CHUNK_CHAR_LIMIT) -> list[str]:
    """Split a section's body at its natural sub-unit boundaries (lines: 항/호 for
    Korean, lettered/numbered subsections for US) and pack them into focused
    chunks. Short sections pass through as one chunk. This is the key to recall:
    a long statute (e.g. 도로교통법 제49조) no longer buries one clause inside a
    huge blob — each subsection lands in its own searchable chunk."""
    if len(text) <= limit:
        return [text.strip()] if text.strip() else []
    lines = [ln for ln in text.split('\n') if ln.strip()]
    chunks, cur = [], ''
    for ln in lines:
        if len(ln) > limit:
            if cur:
                chunks.append(cur); cur = ''
            chunks.extend(_split_long_line(ln, limit))
            continue
        if cur and len(cur) + 1 + len(ln) > limit:
            chunks.append(cur); cur = ln
        else:
            cur = (cur + '\n' + ln) if cur else ln
    if cur:
        chunks.append(cur)
    return chunks or ([text.strip()] if text.strip() else [])


def section_header(section: dict) -> str:
    """Jurisdiction + breadcrumb + section name — the words users actually search
    for. Prefixed onto EVERY chunk so each one carries its own context."""
    parts = []
    j = section.get('jurisdiction', {})
    where = ', '.join(filter(None, [j.get('city'), j.get('county'), j.get('state')]))
    if where:
        parts.append(f'[{where}]')
    if section.get('breadcrumb'):
        parts.append(section['breadcrumb'])
    if section.get('section_name'):
        parts.append(section['section_name'])
    return '\n'.join(parts)


def chunk_section(section: dict) -> list[str]:
    """Final chunks the embedder sees: header + a focused slice of the body."""
    header = section_header(section)
    out = []
    for c in chunk_body(section.get('text', '') or ''):
        out.append((header + '\n' + c).strip() if header else c)
    return out or ([header] if header else [])


# Back-compat: old single-document builder (used by some callers/tests).
def build_document(section: dict) -> str:
    header = section_header(section)
    body = section.get('text', '')
    return (header + '\n' + body) if header else body


def chunk_text(text: str, limit: int = CHUNK_CHAR_LIMIT, overlap: int = CHUNK_OVERLAP):
    return chunk_body(text, limit)


def ingest(data_dir: Path, db_path: Path, collection_name: str, reset: bool):
    client = chromadb.PersistentClient(
        path=str(db_path),
        settings=Settings(anonymized_telemetry=False),
    )

    if reset:
        try:
            client.delete_collection(collection_name)
            print(f'Reset collection: {collection_name}')
        except Exception:
            pass

    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name='all-MiniLM-L6-v2'
    )

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embed_fn,
        metadata={'hnsw:space': 'cosine'},
    )

    json_files = sorted(data_dir.glob('*.json'))
    if not json_files:
        print(f'No JSON files in {data_dir}. Run enrich.py first.')
        return

    BATCH = 128
    ids, docs, metas = [], [], []
    total = 0
    seen_ids = set()   # guard against duplicate section_ids (e.g. law versions)

    for src in json_files:
        sections = json.loads(src.read_text(encoding='utf-8'))
        # Korean statutes go to the multilingual `laws_kr` collection via
        # ingest_kr.py — the English embedder here can't represent Korean.
        sections = [s for s in sections
                    if (s.get('jurisdiction', {}).get('country', '') or '').upper() != 'KR']
        if not sections:
            continue
        print(f'  {src.name}: {len(sections)} sections')
        for sec in sections:
            chunks = chunk_section(sec)
            for i, chunk in enumerate(chunks):
                j = sec.get('jurisdiction', {})
                meta = {
                    'section_id': sec.get('section_id', ''),
                    'section_name': sec.get('section_name', ''),
                    'breadcrumb': sec.get('breadcrumb', ''),
                    'page_start': int(sec.get('page_start', 0) or 0),
                    'source_file': sec.get('source_file', src.stem),
                    'source_title': j.get('source_title', ''),
                    'source_url': j.get('source_url', ''),
                    'level': j.get('level', ''),
                    'city': j.get('city', ''),
                    'county': j.get('county', ''),
                    'state': j.get('state', ''),
                    'country': j.get('country', 'US'),
                    'chunk_index': i,
                }
                doc_id = f'{sec.get("source_file", src.stem)}::{sec.get("section_id", "?")}::{i}'
                if doc_id in seen_ids:
                    continue   # skip duplicate (keeps the first occurrence)
                seen_ids.add(doc_id)
                ids.append(doc_id)
                docs.append(chunk)
                metas.append(meta)

                if len(ids) >= BATCH:
                    collection.upsert(ids=ids, documents=docs, metadatas=metas)
                    total += len(ids)
                    ids, docs, metas = [], [], []

    if ids:
        collection.upsert(ids=ids, documents=docs, metadatas=metas)
        total += len(ids)

    count = collection.count()
    print(f'\nIngested {total} new/updated chunks.')
    print(f'Collection "{collection_name}" now holds {count} chunks total at {db_path}.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data_enriched')
    ap.add_argument('--db', default='vectordb')
    ap.add_argument('--collection', default='laws')
    ap.add_argument('--reset', action='store_true')
    args = ap.parse_args()

    ingest(Path(args.data_dir), Path(args.db), args.collection, args.reset)


if __name__ == '__main__':
    main()
