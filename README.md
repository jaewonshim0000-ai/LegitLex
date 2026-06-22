# ⚖️ LegitLex

**Know what's legal — right where you stand.**

LegitLex is a hyper-local legal compliance assistant. Ask a plain-language
question, point your camera at a situation, or paste a complaint, and it tells
you what the law actually says **for your exact location** — grounded in real
city, county, state, and federal (US) and national (Korea) legal codes, with
citations, confidence scores, and an honest hand-off to a human when it isn't
sure.

🔗 **Live app:** https://lexlocator.fly.dev

> ⚠️ **Legal information, not legal advice.** LegitLex explains the law from its
> dataset; it does not replace a licensed attorney. Verify before you act.

---

## Why

Riding an e-scooter without a license is legal in much of the United States and
illegal in Korea. You can find that out the way our team did — a fine and a
warning from the police — or you can open an app. The law is technically public,
but in practice it's locked away in codes nobody reads, and people break small
rules every day without ever knowing. LegitLex makes the law something you can
check *before* it costs you.

---

## Features

- **Ask a question** — natural-language questions get a verdict (*allowed /
  not allowed / conditional / unknown*) with a confidence score, the potential
  penalty, a plain-English explanation, and exact citations.
- **"Why this verdict?"** — a transparency panel showing the exact statute
  sections retrieved, ranked by semantic match. Nothing outside that list is used.
- **Photo → laws** — take or upload a photo (a scooter on a sidewalk, a dog
  off-leash, a posted sign) and the AI identifies what's legally relevant and
  lists the local laws that apply, in plain language.
- **Complaint analyzer** — paste or upload a complaint and see which provisions
  apply and whether it holds up.
- **Compare locations** — see how the same activity is treated in two places.
- **Ask a Lawyer** — when confidence is low or the law is unclear, LegitLex says
  so and hands you off to real help (legal aid, the bar association, the relevant
  government office) for your jurisdiction.
- **Compliance snapshot** — generate a timestamped record of any answer.
- **Bilingual & multi-level** — US (city → county → state → federal) and Korea
  (national statutes), with location-aware routing.
- **Installable PWA** — works like a native app on phone or desktop; renders a
  device mockup on desktop and full-screen on mobile.

---

## How it works

LegitLex is a **retrieval-augmented generation (RAG)** pipeline with location as
the organizing context.

```
question + location ──► embed ──► vector search (jurisdiction-routed)
                                        │
                          retrieved statute sections (real text only)
                                        │
                              Claude (forced tool-call)
                                        │
        verdict · confidence · penalty · plain-language · citations
```

- **Grounding:** the model is instructed to answer **only** from retrieved
  statute text and never invent a section — this is the core hallucination
  guardrail.
- **Bilingual retrieval:** two separate embedding collections (English and
  multilingual) with country-aware routing, because one model can't embed both
  languages well.
- **Vision:** the photo feature uses the LLM's native vision to describe the
  scene, then runs the same retrieval + grounded-explanation steps.

---

## Tech stack

| Layer | Choice |
|---|---|
| LLM | **Claude Haiku 4.5** (Anthropic) — verdicts, vision, structured output; OpenRouter (`gpt-4o-mini`) as fallback |
| Embeddings | `all-MiniLM-L6-v2` (English) · `paraphrase-multilingual-MiniLM-L12-v2` (Korean) |
| Vector store | **ChromaDB** (~93,000 clause-level chunks) |
| Backend | **FastAPI** + Uvicorn (serves the API *and* the UI) |
| Frontend | In-browser React/JSX, installable **PWA** |
| Packaging | **Docker** (vector DB + models baked into the image) |
| Hosting | **Fly.io** (always-on, 2 CPU / 4 GB) |

---

## Data sources

All legal content comes from **official government sources** — no synthetic law.

- **Korea** — national statutes via the official **law.go.kr Open API**
  (Road Traffic Act, Criminal Act, Animal Protection Act, and others).
- **United States** — city & county ordinances, state codes, and federal
  statutes/regulations via official **GovInfo (GPO)** and **Regulations.gov**
  APIs, plus published municipal codes.
- **Geocoding** — `geopy` / Nominatim to turn GPS into a jurisdiction.

Currently covered jurisdictions: **Irvine, CA · Montgomery, AL · Seoul, KR.**

---

## Project structure

```
.
├── lexlocator/              # application package
│   ├── server.py            # FastAPI app — serves UI + all /api routes
│   ├── core.py              # RAG core: retrieval, verdict generation
│   ├── llm.py               # LLM client (Claude preferred, OpenRouter fallback)
│   ├── vision.py            # photo → relevant laws
│   ├── complaint.py         # complaint analysis
│   ├── snapshot.py          # compliance snapshot documents
│   ├── geo.py               # reverse geocoding
│   ├── schemas.py           # Pydantic models
│   └── static/              # PWA frontend (index.html + app/*.jsx)
├── scrape_*.py / fetch_*.py # source-specific scrapers (law.go.kr, GovInfo, …)
├── enrich.py                # jurisdiction metadata enrichment
├── ingest.py                # build the English/US vector collection
├── ingest_kr.py             # build the Korean vector collection
├── data/ · data_enriched/   # source legal text (JSON)
├── vectordb/                # built ChromaDB store (gitignored — rebuild locally)
├── Dockerfile · fly.toml    # deploy config
└── requirements.txt
```

---

## Run it locally

**Prerequisites:** Python 3.11+ and an LLM API key (Anthropic recommended).

```bash
# 1. install deps
pip install -r requirements.txt

# 2. configure your key
cp .env.example .env
#   then edit .env — set ANTHROPIC_API_KEY=sk-ant-...  (preferred)
#   or leave OPENROUTER_API_KEY set to use the fallback path

# 3. build the vector store from the source JSON (one-time, a few minutes)
python ingest.py          # US / English collection
python ingest_kr.py       # Korean collection

# 4. run the app (serves UI + API on http://localhost:8000)
python -m lexlocator.server
```

Open http://localhost:8000.

### Environment variables

| Variable | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | preferred | Claude key (`sk-ant-…`). When set, used for everything. |
| `OPENROUTER_API_KEY` | fallback | Used only if no Anthropic key is set. |
| `LEXLOCATOR_MODEL` | optional | e.g. `claude-haiku-4-5` (default), `claude-sonnet-4-6`. |
| `KR_LAW_OC` | for scraping KR | Your registered law.go.kr OC id. |
| `GOVINFO_API_KEY` / `REGULATIONS_GOV_API_KEY` | for scraping US | Free api.data.gov keys. |

---

## Deploy (Docker / Fly.io)

The Dockerfile bakes the **prebuilt** `vectordb/` and both embedding models into
the image, so the container boots ready to answer (no rebuild at startup).

```bash
# build the vector store first (so it gets baked into the image)
python ingest.py && python ingest_kr.py

# deploy
fly deploy --remote-only -a <your-app>

# set the LLM key as a secret (never commit it)
fly secrets set ANTHROPIC_API_KEY=sk-ant-... LEXLOCATOR_MODEL=claude-haiku-4-5 -a <your-app>
```

The app is configured always-on (`auto_stop_machines = off`, `min_machines_running = 1`)
with 2 CPU / 4 GB so the in-RAM index stays warm. First boot loads the DB +
models (~1–2 min); after that, responses are fast.

---

## Responsible AI

- **Grounded, cited answers.** Every response is built only from retrieved
  statute text, shown with citations and a "Why this verdict?" panel.
- **Confidence + escalation.** Each answer carries a confidence score; when it's
  low or the law is unclear, the **Ask a Lawyer** panel hands users off to real
  legal help instead of guessing.
- **Human-in-the-loop.** LegitLex never decides *whether you should act* — that
  decision, and its consequences, stay with the person (and, for anything
  serious, a licensed attorney).

---

## Disclaimer

LegitLex provides legal **information**, not legal **advice**. It may miss
context or rules not yet in its dataset and can be wrong. Always verify against
the official code and consult a qualified attorney for anything consequential.
