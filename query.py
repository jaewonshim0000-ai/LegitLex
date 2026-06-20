"""
Ask a question about local law. Retrieves matching sections from ChromaDB
(filtered by GPS-derived jurisdiction) and asks Claude to answer with citations.

Usage:
    # Question + explicit city
    python query.py "Is an e-bike legal for a 16 year old?" --city Irvine --state CA

    # Question + GPS coords (reverse-geocoded with Nominatim)
    python query.py "What's the noise curfew?" --lat 33.6846 --lng -117.8265

    # Just retrieval, no LLM call
    python query.py "parking rules" --city Irvine --no-llm
"""
from __future__ import annotations
import os
import argparse
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions


# ---------------------------------------------------------------------------
# Location resolution
# ---------------------------------------------------------------------------

def reverse_geocode(lat: float, lng: float) -> dict:
    """lat/lng -> {city, county, state, country} using free Nominatim."""
    from geopy.geocoders import Nominatim
    geo = Nominatim(user_agent='usaii-law-rag')
    loc = geo.reverse((lat, lng), exactly_one=True, language='en', zoom=14, addressdetails=True)
    if not loc:
        return {}
    a = loc.raw.get('address', {})
    city = a.get('city') or a.get('town') or a.get('village') or a.get('hamlet') or ''
    county = a.get('county', '')
    state_code = a.get('ISO3166-2-lvl4', '')  # e.g. "US-CA"
    state = state_code.split('-')[-1] if state_code else a.get('state', '')
    return {
        'city': city,
        'county': county,
        'state': state,
        'country': a.get('country_code', '').upper() or 'US',
    }


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def get_collection(db_path: Path, name: str):
    client = chromadb.PersistentClient(
        path=str(db_path),
        settings=Settings(anonymized_telemetry=False),
    )
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name='all-MiniLM-L6-v2'
    )
    return client.get_collection(name=name, embedding_function=embed_fn)


def build_filter(city: str, county: str, state: str):
    """Match anything for this user's city OR county OR state OR federal.
    The LLM step decides which level actually applies."""
    clauses = []
    if city:
        clauses.append({'city': city})
    if county:
        clauses.append({'county': county})
    if state:
        clauses.append({'state': state})
    clauses.append({'level': 'federal'})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {'$or': clauses}


def retrieve(collection, query: str, location: dict, k: int = 8):
    where = build_filter(location.get('city', ''), location.get('county', ''), location.get('state', ''))
    res = collection.query(
        query_texts=[query],
        n_results=k,
        where=where,
    )
    hits = []
    for i, doc in enumerate(res['documents'][0]):
        meta = res['metadatas'][0][i]
        dist = res['distances'][0][i] if res.get('distances') else None
        hits.append({'text': doc, 'meta': meta, 'distance': dist})
    return hits


# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a local-law assistant. The user asks a real-world
question; you receive law sections retrieved from city / county / state /
federal codes. Your job:

1. Answer in plain English first (2-4 sentences).
2. Then list the supporting laws as a bulleted citation list. Each citation
   must include: jurisdiction level (city/county/state/federal), the
   jurisdiction name, the section_id, and a one-line paraphrase.
3. If the retrieved sections do not actually answer the question, say so
   explicitly. Do not invent statutes or section numbers. Do not guess.
4. Note any limits: e.g. "this is from the Irvine Municipal Code as of the
   last scrape; federal/state rules may also apply and were not retrieved."
5. End with one line: "Not legal advice."

Format:

**Answer:** ...

**Citations:**
- [city: Irvine, CA] § 1-2-303 - one-line paraphrase
- [state: CA] (not retrieved - mention if relevant)

**Caveats:** ...

Not legal advice.
"""


def format_context(hits: list) -> str:
    blocks = []
    for h in hits:
        m = h['meta']
        where = ', '.join(filter(None, [m.get('city'), m.get('county'), m.get('state')]))
        header = f"[{m.get('level', '?')}: {where}] § {m.get('section_id', '?')}"
        if m.get('section_name'):
            header += f" - {m['section_name']}"
        if m.get('breadcrumb'):
            header += f"\nPath: {m['breadcrumb']}"
        if m.get('source_title'):
            header += f"\nSource: {m['source_title']}"
        blocks.append(f'{header}\n\n{h["text"]}')
    return '\n\n---\n\n'.join(blocks)


def ask_claude(question: str, hits: list, location: dict, model: str) -> str:
    from anthropic import Anthropic
    client = Anthropic()
    where = ', '.join(filter(None, [location.get('city'), location.get('county'), location.get('state')]))
    user_msg = f"""User location: {where or 'unknown'}

User question: {question}

Retrieved law sections:

{format_context(hits)}
"""
    resp = client.messages.create(
        model=model,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': user_msg}],
    )
    return ''.join(block.text for block in resp.content if hasattr(block, 'text'))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('question')
    ap.add_argument('--city', default='')
    ap.add_argument('--county', default='')
    ap.add_argument('--state', default='')
    ap.add_argument('--lat', type=float)
    ap.add_argument('--lng', type=float)
    ap.add_argument('--db', default='vectordb')
    ap.add_argument('--collection', default='laws')
    ap.add_argument('-k', type=int, default=8, help='How many sections to retrieve')
    ap.add_argument('--model', default='claude-sonnet-4-5-20250929',
                    help='Anthropic model id. Override if you have a newer one.')
    ap.add_argument('--no-llm', action='store_true', help='Only show retrieval results')
    args = ap.parse_args()

    location = {'city': args.city, 'county': args.county, 'state': args.state}
    if args.lat is not None and args.lng is not None:
        print(f'Reverse-geocoding ({args.lat}, {args.lng})...')
        location = reverse_geocode(args.lat, args.lng)
        print(f'  Location: {location}')

    collection = get_collection(Path(args.db), args.collection)
    hits = retrieve(collection, args.question, location, k=args.k)

    print(f'\nRetrieved {len(hits)} sections:')
    for h in hits:
        m = h['meta']
        where = ', '.join(filter(None, [m.get('city'), m.get('state')]))
        print(f"  [{m.get('level', '?'):8s}] § {m.get('section_id', '?'):15s} "
              f"({where})  dist={h['distance']:.3f}  {m.get('section_name', '')[:60]}")

    if args.no_llm:
        print('\n(skipped LLM step - --no-llm)')
        return

    if not os.environ.get('ANTHROPIC_API_KEY'):
        print('\nANTHROPIC_API_KEY not set. Set it to call Claude, or pass --no-llm.')
        return

    print('\nAsking Claude...\n')
    answer = ask_claude(args.question, hits, location, args.model)
    print(answer)


if __name__ == '__main__':
    main()
