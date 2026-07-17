# PROJECT_CONTEXT.md

## StyleMate Server — Project Context

### Architecture Overview

FastAPI app with SQLite backend. Key modules:

| Module | Purpose |
|--------|---------|
| `app/pairing_engine.py` | Outfit scoring: color harmony (HSL), FashionCLIP embedding similarity, hard-rule matching |
| `app/style_embeddings.py` | FashionCLIP embedding computation, cosine similarity, zero-shot classification |
| `app/learned_compatibility.py` | Optional: outfit-transformer pretrained compatibility scoring |
| `app/routers/tagging.py` | AI-powered clothing item tagging (FashionCLIP zero-shot by default) |

### Scoring System (Step 4 — Blended Weights)

The core scoring blends three signals:

| Component | Weight | Source |
|-----------|--------|--------|
| Color harmony | 50% | HSL-based hue distance, neutral detection, fashion clashing |
| FashionCLIP similarity | 35% | Cosine similarity of CLIP image embeddings |
| Hard rules | 15% | Occasion/formality match, target_gender compatibility |

### Optional: Learned Compatibility (Step 6)

When `USE_LEARNED_COMPATIBILITY=true` in `.env`, the engine uses an alternate
weight set that blends in the outfit-transformer pretrained score:

| Component | Weight |
|-----------|--------|
| Learned compatibility | 40% |
| Color harmony | 30% |
| FashionCLIP similarity | 20% |
| Hard rules | 10% |

#### Setup (optional — skip if too slow or you lack disk space)

1. The outfit-transformer repo is already cloned at `third_party/outfit-transformer/`
2. Download the checkpoint (~500MB):
   ```bash
   ./scripts/download_checkpoint.sh
   ```
3. Enable in `.env`:
   ```
   USE_LEARNED_COMPATIBILITY=true
   ```

#### Performance Notes

- First load: ~5-10s (model + CLIP on CPU)
- Per-pair scoring: ~1-3s on CPU
- For a 3-item outfit (3 pairs): ~3-9s total
- Requires ~1GB additional RAM for the model
- Without this enabled, scoring uses the Step 4 weights and is instant

#### Toggle Off

Set `USE_LEARNED_COMPATIBILITY=false` (or remove it) in `.env`. The engine
falls back to the Step 4 weights with zero overhead.

### Tagging Provider

By default, tagging uses **FashionCLIP zero-shot classification** (local, free,
no rate limits). Set `TAGGING_PROVIDER` in `.env` to switch:

| Value | Behavior |
|-------|----------|
| `fashion_clip` (default) | Local zero-shot classification via FashionCLIP. No API key needed, no rate limits, no cost. |
| `vision_api` | Calls Google Gemini API (gemini-2.5-flash). Requires `GEMINI_API_KEY` in `.env`. Free tier is rate-limited to ~1,500 req/day — use as secondary/enrichment path. |

All external API calls are wrapped with `call_with_retry` (exponential backoff on 429/5xx).
