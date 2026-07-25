# StyleMate — Technical Summary

## 1. Style/Category Detection (`server/app/style_match.py`)

### Core functions/classes

| Function | Purpose |
|---|---|
| `generate_style_match(item_id, db)` | Main entry — given a selected item, returns matching wardrobe items + purchase suggestions + color advice + shopping links |
| `_generated_suggestions(...)` | Builds purchase suggestions using occasion-aware templates scored via `score_pair()` |
| `_apply_style_diversity(...)` | Caps neutral items, lets colorful/trendy items through at a lower threshold |
| `_recommend_avoid_colors(...)` | Returns recommended/avoid colors using HSL color theory |
| `_occasion_ideas(...)` | Generates 3 outfit idea names for the selected item's occasion |
| `_build_shop_links(query)` | Builds Meesho/Myntra/Ajio/Amazon/Flipkart search URLs |
| `build_item_match_queries(...)` | Returns search queries for each matching category |
| `StyleMatchResult` | Dataclass — main output structure |
| `StyleMatchItem` | Dataclass — individual match (name, percentage, reason, owned/not) |

### How detection works — **Rule-based + FashionCLIP embeddings + Color theory**

The system does **NOT** use an LLM for matching. It uses:

1. **Color theory (HSL math)**: `_color_to_hsl()` maps named colors → HSL triples. `score_pair_color()` computes harmony (complementary/analogous/triadic/neutral/clashing) via hue distance.
2. **FashionCLIP embeddings**: `patrickjohncyh/fashion-clip` on HuggingFace generates image embeddings stored in `embedding_json` column. `_embedding_similarity()` computes cosine similarity between items.
3. **Hard rules**: Occasion/formality matching via `_hard_rule_score()`.
4. **Fabric/fit/season scoring**: Affinity/clash tables + fit contrast matrix + season compatibility.
5. **Body-type style scoring**: YAML-driven boosts for style tags per body type.
6. **All combined in `score_pair()`** with weights:
   - Color: 35% | Embedding: 25% | Hard rules: 15% | Fabric: 10% | Fit: 8% | Season: 7% | Style tag: 7%

Category pairing rules are hardcoded (`_MATCHING_CATEGORIES`): e.g. a "top" pairs with bottom, footwear, accessory, outerwear.

### Input/Output example

**Input** → `GET /style-match?item_id=42`

**Output** (simplified JSON contract):
```json
{
  "selectedItem": { "id": 42, "name": "Blue Shirt", "category": "top", ... },
  "matchingBottoms": [
    { "name": "Black Jeans", "match_percentage": 85, "reason": "Complementary colors...", "owned": true, "item_id": 15, "image_url": "..." }
  ],
  "matchingTops": [...],
  "matchingFootwear": [...],
  "matchingAccessories": [...],
  "layeringSuggestions": [...],
  "recommendedColors": ["navy", "black", "beige"],
  "avoidColors": ["neon green"],
  "occasionOutfits": [{"name": "Office Casual", "based_on": "Blue Shirt"}, ...],
  "shoppingSuggestions": [
    { "category": "bottom", "item_name": "Black Jeans", "shopping_links": [
      {"store": "meesho", "url": "..."},
      {"store": "myntra", "url": "..."}
    ]}
  ],
  "alreadyOwned": [...]
}
```

Score threshold: `MATCH_THRESHOLD = 70%`. Items below that are excluded.

---

## 2. Database Setup

| Property | Value |
|---|---|
| **Type** | PostgreSQL (via Supabase) with SQLite fallback for local dev |
| **ORM** | SQLAlchemy with Alembic migrations |
| **Connection** | `.env` → `DATABASE_URL`. If not set, falls back to `sqlite:///./stylemate.db` |
| **Tables** | `users`, `clothing_items`, `calendar_entries`, `try_on_results`, `try_on_usage`, `outfit_feedback` |

### Key schema — `clothing_items`

```python
class ClothingItem(Base):
    __tablename__ = "clothing_items"

    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    image_url     = Column(String)         # URL or path to image
    category      = Column(String)          # top, bottom, dress, outerwear, footwear, accessory, kurti
    color         = Column(String)          # named color ("blue", "black", etc.)
    pattern       = Column(String)          # solid, striped, printed, checked
    occasion_tag  = Column(String)          # comma-separated: "casual,office"
    season        = Column(String)          # spring, summer, fall, winter, all-season
    brand         = Column(String)
    name          = Column(String)
    formality     = Column(String)
    target_gender = Column(String)          # men, women, unisex
    fabric_type   = Column(String)          # cotton, denim, silk, wool, leather, etc.
    fit_type      = Column(String)          # slim, regular, oversized, loose
    sleeve_length = Column(String)          # sleeveless, short, three_quarter, long
    formality_score = Column(Integer)       # 1-5
    tags          = Column(Text)            # freeform text
    style_tags    = Column(Text)            # JSON list: ["belted", "structured", ...]
    embedding_json = Column(Text)           # FashionCLIP embedding (JSON float array)
```

**Attributes are structured** — color, fabric, fit, season, occasion, etc. are all individual columns. The `embedding_json` field is the unstructured blob (FashionCLIP vector).

---

## 3. Online Shopping / Product Search Integration

### Three tiers of shopping functionality:

#### Tier 1: Search URLs (no API calls)
`style_match.py` builds plain search URLs for Meesho/Myntra/Ajio/Amazon/Flipkart/Google Shopping. These are deep links — no scraping, no pricing.

```python
_SHOP_BUILDERS = {
    "meesho": "https://www.meesho.com/search?q=",
    "myntra": "https://www.myntra.com/",
    "ajio": "https://www.ajio.com/search/",
    "amazon": "https://www.amazon.in/s?k=",
    "flipkart": "https://www.flipkart.com/search?q=",
}
```

Called in `_build_shop_links()` → returns `[{store, url}, ...]`.

#### Tier 2: Flipkart Affiliate API (real product results)
`shopping_service.py` → `FlipkartProvider` hits the Flipkart Affiliate API (`affiliate-api.flipkart.net/affiliate/1.0/search.json`) with `FLIPKART_AFFILIATE_ID` / `FLIPKART_AFFILIATE_TOKEN` from `.env`. Returns real products with name, image, price, affiliate link. Cached with TTLCache (30 min). Has retry logic via tenacity.

**Note**: Currently disabled in `.env` (credentials are empty).

#### Tier 3: Concurrent multi-provider search
`search_all_providers()` in `shopping_service.py` queries all active providers (configured via `SHOPPING_PROVIDERS` env var) concurrently with `asyncio.gather`. Results tagged by source platform.

**Meesho provider**: Returns a single search link (no API). **Amazon provider**: Returns a single search link with optional affiliate tag.

### Shopping flow

| Endpoint | What it does |
|---|---|
| `GET /shopping-suggestions?user_id=X` | Detects wardrobe gaps (`find_gaps`), builds search queries, queries top provider |
| `GET /items/{id}/shop-matches` | Builds per-category queries for a selected item, queries all providers concurrently, ranks results by FashionCLIP visual similarity (`rank_by_visual_fit`) |

`rank_by_visual_fit()` compares the selected item's FashionCLIP embedding against product image embeddings and sorts by cosine similarity. **There is no external scraper** for general product search — only Flipkart's official affiliate API.

---

## 4. General Stack

| Layer | Technology |
|---|---|
| **Framework** | FastAPI (Python 3.10+) |
| **Server** | uvicorn |
| **ORM** | SQLAlchemy + Alembic |
| **DB** | PostgreSQL (Supabase) / SQLite (local) |
| **Image tagging** | **FashionCLIP** (`patrickjohncyh/fashion-clip`) via HuggingFace transformers (default, free, no rate limits) OR **Gemini Vision API** (opt-in via `TAGGING_PROVIDER=vision_api`) |
| **Image embeddings** | FashionCLIP → stored as JSON in `embedding_json` column |
| **Image storage** | Pluggable: **Local** (default, `server/uploads/`), **Supabase Storage** (current config), **S3**, **GCS** |
| **Background tasks** | Celery + Redis (for try-on async processing) |
| **ML recommend** | LightFM (collaborative filtering, ramps up as user feedback grows) |
| **Config files** | YAML (`config/body_type_rules.yaml`) — body-type → style-tag boost rules |

### How images flow
1. Upload → `/upload-image` → file saved via `StorageProvider` → returns `image_url`
2. Image auto-tagged via `_tag_item_fashion_clip()` → category, color, pattern, fabric, fit, sleeve, occasion, season, gender, style_tags all extracted via FashionCLIP zero-shot classification
3. Embedding computed in background thread → `compute_and_store_embedding()` → stored in `embedding_json`
4. Matching uses both structured attributes (color, fabric, etc.) + embedding similarity

### File structure (server)
```
server/
├── app/
│   ├── main.py              # FastAPI app, routers, startup
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── database.py          # DB connection (Postgres/SQLite)
│   ├── pairing_engine.py    # Core scoring: score_pair(), score_outfit(), suggest_outfits()
│   ├── style_match.py       # Single-item style match engine
│   ├── style_embeddings.py  # FashionCLIP embedding compute + zero-shot classification
│   ├── shopping_service.py  # Flipkart/Meesho/Amazon providers
│   ├── shopping_links.py    # Search URL builders
│   ├── storage.py           # Local/S3/GCS/Supabase storage abstraction
│   ├── try_on_service.py    # Virtual try-on (FAL/HF/Gemini providers)
│   ├── recommender.py       # LightFM collaborative filtering
│   ├── tasks.py             # Celery async tasks
│   └── routers/
│       ├── tagging.py       # Image auto-tagging endpoint
│       ├── upload.py         # Image upload endpoint
│       ├── shop_matches.py   # Item → shopping matches with visual ranking
│       ├── shopping.py       # Wardrobe gap → shopping suggestions
│       ├── style_match.py    # Style match endpoint
│       └── ...
└── config/
    └── body_type_rules.yaml # Body-type style tag boosts
```
