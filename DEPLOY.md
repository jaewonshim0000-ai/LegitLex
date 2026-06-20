# Deploying LegitLex as a real app

LegitLex is **one container**: FastAPI serves the mobile web UI *and* the API, with
the 93,567-chunk vector store and both embedding models baked into the image. No
ingest step, no model download at runtime — it boots ready to answer. The UI is a
**PWA**, so once it's live at an HTTPS URL, anyone can "Add to Home Screen" and it
behaves like an installed app (own icon, full-screen, offline shell).

> **Sizing reality:** the multilingual embedding model + the vector store need
> **~1 GB RAM**. Pick an instance with at least that. The image is large (~2.5 GB)
> because the model weights + 1.4 GB DB ship inside it.

---

## What you set as a secret (never commit this)
Only one var is needed at runtime:

| Key | Value |
|-----|-------|
| `OPENROUTER_API_KEY` | your `sk-or-v1-…` key (already in your local `.env`) |
| `LEXLOCATOR_MODEL` | *(optional)* defaults to `openai/gpt-oss-120b:free` |

The `.env` file is **git/Docker-ignored** and is **not** baked into the image.

---

## Option A — Fly.io  (recommended: ships your local 1.4 GB DB directly)

1. Install the CLI and sign in (creates your account in the browser):
   ```bash
   # Windows (PowerShell):  iwr https://fly.io/install.ps1 -useb | iex
   # macOS/Linux:           curl -L https://fly.io/install.sh | sh
   fly auth login
   ```
2. From the project folder, claim an app name + region (updates `fly.toml`):
   ```bash
   fly launch --no-deploy
   ```
3. Set your API key as a secret:
   ```bash
   fly secrets set OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx
   ```
4. Deploy (builds the image with the DB + models, pushes, runs):
   ```bash
   fly deploy
   ```
5. Open it:
   ```bash
   fly open
   ```

Your phone: visit the `https://<app>.fly.dev` URL → browser menu → **Add to Home Screen**.

> Fly's 1 GB `shared-cpu-1x` is roughly $5–7/mo. `auto_stop_machines` (already set in
> `fly.toml`) scales it to zero when idle so you only pay for active time.

---

## Option B — Render (Docker)

Render builds from a connected **Git repo** — but your 1.4 GB `vectordb/` is
git-ignored, so a plain Render build won't have the data. Two ways around it:

- **Easiest:** deploy on Fly (Option A), which ships local files.
- **On Render:** create a **Web Service → Docker**, attach a **Persistent Disk**
  (≥3 GB) mounted at `/app/vectordb`, and run `python ingest.py && python ingest_kr.py`
  once (e.g. via a one-off shell) to build the DB on the disk. Set `OPENROUTER_API_KEY`
  in the dashboard. Use the **Standard** instance (2 GB RAM) — the free 512 MB tier
  is too small for the multilingual model.

---

## Test the container locally first (optional but recommended)
```bash
docker build -t legitlex .
docker run --rm -p 8000:8000 -e OPENROUTER_API_KEY=sk-or-v1-xxxx legitlex
# open http://localhost:8000
```

---

## Custom domain (optional)
- Fly: `fly certs add app.yourdomain.com`, then add the shown DNS records.

## Slimmer / cheaper variant
If 1 GB feels heavy, you can drop Korean support to shed the big multilingual model:
remove the `paraphrase-multilingual-MiniLM-L12-v2` line from the Dockerfile's
pre-download step and skip the `laws_kr` collection. US-only then fits comfortably in
512 MB. (Ask and I can wire a `KR_DISABLED` flag.)
