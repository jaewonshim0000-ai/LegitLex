---
title: LegitLex
emoji: ⚖️
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 8000
pinned: false
short_description: Hyper-local legal compliance, with citations
---

# LegitLex

Hyper-local legal compliance answers, grounded in real city / county / state /
federal (US) and national (Korea) law, with citations. GPS-aware RAG over a
93k-chunk vector store; "not legal advice" safeguards and hallucination
prevention built in.

Single container: FastAPI serves both the mobile PWA and the API. The vector
store and embedding models are baked into the image, so it boots ready to answer.

**Set one secret** in *Settings → Variables and secrets*: `OPENROUTER_API_KEY`.
