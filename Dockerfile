# LegitLex — single container: FastAPI serves the UI + the API. The vector DB is
# REBUILT from the committed source JSON at image-build time, so the 1.1 GB DB
# never needs to live in git — the repo stays GitHub-friendly and deploys to Fly.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch (smaller than the default CUDA build), then the rest.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch
COPY requirements.txt .
RUN pip install -r requirements.txt

# Pre-download both embedding models (US = all-MiniLM, Korea = multilingual).
RUN python -c "from sentence_transformers import SentenceTransformer as S; S('all-MiniLM-L6-v2'); S('paraphrase-multilingual-MiniLM-L12-v2')"

# App code + source law JSON + the ingest scripts.
COPY lexlocator ./lexlocator
COPY ingest.py ingest_kr.py ./
COPY data_enriched ./data_enriched

# Build the vector store INSIDE the image from the committed JSON. This embeds
# ~93k US chunks (laws) + ~1k Korean chunks (laws_kr). Cached by Docker unless
# data_enriched/ changes, so repeat deploys are fast.
RUN python ingest.py --reset --data-dir data_enriched --db vectordb \
 && python ingest_kr.py --reset --data-dir data_enriched --db vectordb

# Let the runtime user read the app and write ChromaDB's lock/WAL files.
RUN chmod -R a+rwX /app/vectordb && chmod -R a+rX /app/lexlocator

EXPOSE 8000
CMD ["sh", "-c", "uvicorn lexlocator.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
