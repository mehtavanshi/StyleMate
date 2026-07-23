# StyleMate

An **AI-powered wardrobe management and outfit suggestion app**. It helps users catalog their clothing, automatically tag items using AI, get personalized outfit suggestions, virtually "try on" outfits on their body photo, plan outfits on a calendar, and get shopping recommendations.

Built with two parts:

- **`/app`** — React Native mobile app built with [Expo](https://expo.dev) and [Expo Router](https://docs.expo.dev/router/introduction/), written in TypeScript.
- **`/server`** — Python backend built with [FastAPI](https://fastapi.tiangolo.com), using [SQLAlchemy](https://www.sqlalchemy.org) with a SQLite database, Celery + Redis for async tasks.

```
StyleMate/
├── app/       # Expo React Native mobile app
└── server/    # FastAPI Python backend
```

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Folder Structure](#folder-structure)
- [Project Flow](#project-flow)
- [API Documentation](#api-documentation)
- [AI Workflow](#ai-workflow)
- [Database Design](#database-design)
- [State Management](#state-management)
- [Authentication & Privacy](#authentication--privacy)
- [Error Handling](#error-handling)
- [Performance](#performance)
- [Security](#security)
- [Setup Instructions](#setup-instructions)
- [Environment Variables](#environment-variables)
- [Running the Project](#running-the-project)
- [Testing](#testing)
- [Future Improvements](#future-improvements)
- [Troubleshooting](#troubleshooting)
- [FAQ](#frequently-asked-questions)

---

## Project Overview

### What problem does it solve?

"I have a closet full of clothes but nothing to wear." StyleMate eliminates outfit decision paralysis by:

1. **Cataloging** your wardrobe via photo with AI auto-tagging
2. **Suggesting outfits** using color harmony, style embeddings, body-type rules, and ML
3. **Virtual try-on** — see how outfits look on your body without wearing them
4. **Calendar planning** — lock outfits to specific dates and occasions
5. **Gap detection** — know what's missing from your wardrobe with shopping links
6. **Style matching** — given one item, find all complementary pieces

### Target Users

- Fashion-conscious mobile users (Indian market focus with Flipkart/Meesho/Amazon integrations)
- Both men and women (gender-aware recommendations)
- Anyone with a wardrobe who wants AI-powered outfit suggestions

### Major Features

| Feature | Description |
|---------|-------------|
| **Wardrobe Catalog** | Add items via photo, AI auto-tags category/color/pattern/occasion/season/fabric/fit/formality |
| **AI Outfit Suggestions** | 7-signal scoring engine: color harmony + FashionCLIP embeddings + hard rules + fabric + fit + season + style tags |
| **Virtual Try-On** | IDM-VTON rendering via FAL.ai / Fashn / Kling / self-hosted / free HuggingFace Space |
| **Calendar Planning** | Lock outfits to dates, filter by occasion, plan ahead |
| **Style Match** | Single-item analysis: complementary pieces, recommended colors, shopping links |
| **Shopping Integration** | Gap detection + multi-provider search (Meesho, Flipkart, Amazon) with visual similarity ranking |
| **AI Style Advice** | Gemini-powered outfit explanations and shoe/accessory/layering recommendations |
| **Body Type Personalization** | Onboarding questionnaire + style tag scoring boosts per body shape |
| **Feedback Loop** | Like/dislike suggestions → LightFM collaborative filtering learns preferences over time |
| **Privacy-First** | GDPR-style consent flow, photo retention policies, delete-everything option |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     STYLEMATE ARCHITECTURE                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────┐     ┌───────────────────────────┐  │
│  │   FRONTEND (Mobile)     │     │    BACKEND (API Server)    │  │
│  │   React Native + Expo   │◄───►│    Python FastAPI           │  │
│  │   TypeScript            │     │    SQLAlchemy + SQLite       │  │
│  │   Expo Router (6 tabs)  │     │    Pydantic validation      │  │
│  └────────────┬────────────┘     └──────────┬────────────────┘  │
│               │         HTTP/REST            │                    │
│               └──────────────────────────────┘                    │
│                                      │                            │
│                  ┌───────────────────┼─────────────────┐         │
│                  │                   │                 │         │
│            ┌─────▼──────┐    ┌──────▼───────┐  ┌─────▼─────┐  │
│            │ AI Models   │    │  Background  │  │  Storage   │  │
│            │             │    │  Tasks       │  │            │  │
│            │ FashionCLIP │    │  Celery      │  │  Local     │  │
│            │ (local CPU) │    │  + Redis     │  │  S3        │  │
│            │ Gemini API  │    │              │  │  GCS       │  │
│            │ LightFM     │    │              │  │            │  │
│            │ outfit-     │    │              │  │            │  │
│            │ transformer │    │              │  │            │  │
│            └─────────────┘    └──────────────┘  └────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                EXTERNAL SERVICES                          │   │
│  │  FAL.ai / Fashn.ai / Kling (Virtual Try-On Providers)    │   │
│  │  Flipkart Affiliate / Meesho / Amazon (Shopping)         │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### Component Communication

| Connection | Protocol | Details |
|-----------|----------|---------|
| Frontend ↔ Backend | REST API (HTTP/JSON) | Base URL per platform in `app/config/api.ts` |
| Backend → FashionCLIP | Local inference | PyTorch model loaded on startup, runs on CPU |
| Backend → Gemini | HTTPS API | Used for tagging (optional) and style advice |
| Backend → Celery | Redis broker | Async virtual try-on jobs with polling |
| Backend → Shopping APIs | HTTP | Concurrent requests to Flipkart (API), Meesho/Amazon (links) |
| Backend → Try-On Providers | HTTPS | FAL.ai, Fashn.ai, Kling, or self-hosted IDM-VTON |
| Backend → Storage | Filesystem/S3/GCS | Pluggable via `STORAGE_PROVIDER` env var |

### Why This Architecture

- **SQLite** — Zero-config, perfect for dev/demo. SQLAlchemy ORM makes swapping to PostgreSQL trivial.
- **FastAPI** — Async-native, auto-generates Swagger docs at `/docs`, Pydantic validation.
- **React Native + Expo** — Cross-platform mobile with one codebase. Expo ecosystem provides camera, file system, location, sharing.
- **FashionCLIP locally** — No paid API needed for image tagging. Runs on CPU (~2-5s per image).
- **Celery + Redis** — Virtual try-on takes 10-30s, so it runs async with job status polling.
- **Provider abstraction** — Every external service (storage, try-on, shopping) uses the Strategy pattern for easy swapping.

---

## Technology Stack

### Frontend

| Technology | What It Is | Why It's Used |
|-----------|-----------|---------------|
| **React Native** | Cross-platform mobile framework | Single codebase for iOS + Android |
| **Expo** (~54) | React Native toolchain | Simplifies build, camera, file system, image picker |
| **Expo Router** (~6) | File-based routing | Convention-based navigation, tabs, stacks |
| **TypeScript** (~5.9) | Typed JavaScript | Type safety, better IDE support, fewer runtime errors |
| **React** (19.1) | UI library | Component-based UI |
| **react-hook-form** | Form management | Efficient form state for the add-item multi-step form |
| **react-native-calendars** | Calendar component | Date picker for outfit planning |
| **react-native-reanimated** | Animations | Smooth UI transitions |
| **react-native-safe-area-context** | Safe area handling | Notch/status bar compatibility |
| **react-native-svg** | SVG rendering | Body silhouette overlay, body shape icons |
| **lucide-react-native** | Icon library | Consistent icons across all screens |
| **expo-camera** | Camera access | Photo capture for items and body photos |
| **expo-image-picker** | Gallery access | Pick existing photos |
| **expo-image-manipulator** | Image processing | Crop, rotate, resize before upload |
| **expo-media-library** | Device media | Save try-on results |
| **expo-sharing** | Share sheet | Share try-on results |
| **expo-file-system** | File operations | Local file handling for uploads |
| **@infinitered/react-native-mlkit-object-detection** | On-device ML | Body detection for photo validation |
| **@react-native-async-storage/async-storage** | Local key-value store | Onboarding completion flag |

### Backend

| Technology | What It Is | Why It's Used |
|-----------|-----------|---------------|
| **Python** (3.9+) | Programming language | Rich ML/AI ecosystem |
| **FastAPI** | Async Python web framework | High performance, auto-docs, Pydantic integration |
| **SQLAlchemy** | Python ORM | Database abstraction, relationships, migrations |
| **SQLite** | File-based database | Zero-config for development |
| **Pydantic** | Data validation | Request/response schemas with type checking |
| **Uvicorn** | ASGI server | Fast async server for FastAPI |
| **Celery** | Distributed task queue | Async virtual try-on rendering |
| **Redis** | In-memory data store | Celery broker for job queues |
| **httpx** | Async HTTP client | API calls to external services |
| **python-dotenv** | Env file loader | Load `.env` configuration |
| **python-multipart** | Multipart parsing | File upload handling |

### AI / ML

| Technology | What It Is | Why It's Used |
|-----------|-----------|---------------|
| **FashionCLIP** (`patrickjohncyh/fashion-clip`) | Fashion-specific vision-language model | Zero-shot image tagging, style embeddings, visual similarity (runs locally) |
| **Gemini API** (`gemini-3.1-flash-lite`) | Google's multimodal AI | Optional tagging backend + AI style advice/explanations |
| **LightFM** | Collaborative filtering library | Learns outfit preferences from like/dislike feedback |
| **implicit** | ALS recommendation library | Fallback collaborative filtering if LightFM unavailable |
| **outfit-transformer** (optional) | Polyvore-pretrained model | Learned outfit compatibility scoring |
| **PyTorch** | Deep learning framework | Runs FashionCLIP and outfit-transformer |
| **transformers** (HuggingFace) | Model loading | Loads FashionCLIP model |
| **scikit-learn** | ML utilities | Feature engineering for recommender |
| **scipy** | Sparse matrices | Interaction matrices for collaborative filtering |
| **colorthief** | Color extraction | Extracts dominant color from item images |
| **Pillow** | Image processing | Image loading for FashionCLIP |
| **NumPy** | Numerical computing | Embedding operations |

### Storage & Infrastructure

| Technology | What It Is | Why It's Used |
|-----------|-----------|---------------|
| **Local filesystem** | Default file storage | Dev/simple deployment |
| **AWS S3** (optional) | Cloud object storage | Production photo storage |
| **Google Cloud Storage** (optional) | Cloud object storage | Alternative cloud storage |
| **gradio_client** | HuggingFace Spaces client | Free virtual try-on via public HF Spaces |
| **cachetools** | In-memory caching | TTLCache for shopping results, try-on cache |
| **tenacity** | Retry library | Exponential backoff for API calls |
| **PyYAML** | YAML parser | Body type rule configuration |

---

## Folder Structure

### Root Level

```
StyleMate/
├── app/                    # React Native mobile app (Expo)
├── server/                 # Python FastAPI backend
├── PROJECT_CONTEXT.md      # Project overview & feature roadmap
├── plan.md                 # Detailed improvement plan & build prompts
├── step1_plan.md           # FashionCLIP integration plan
└── README.md               # This file
```

### Frontend (`/app`)

```
app/
├── app/                        # Expo Router file-based screens
│   ├── _layout.tsx             # Root Stack navigator (wraps everything)
│   ├── (tabs)/                 # Bottom tab group
│   │   ├── _layout.tsx         # 6-tab layout definition
│   │   ├── index.tsx           # Home dashboard — outfit of the day, stats, photo
│   │   ├── wardrobe.tsx        # Wardrobe grid — filterable 2-column grid
│   │   ├── add-item.tsx        # Add item — multi-step form with AI tagging
│   │   ├── outfit-suggestions.tsx  # Outfit suggestions — cards, try-on, shopping
│   │   ├── calendar.tsx        # Calendar planner — lock outfits to dates
│   │   └── my-tryons.tsx       # Try-on gallery — past results
│   ├── capture.tsx             # Camera/gallery photo capture with validation
│   ├── consent.tsx             # GDPR-style privacy consent
│   ├── privacy.tsx             # Privacy policy display
│   ├── settings.tsx            # Photo & privacy settings
│   ├── try-on.tsx              # Try-on result display with save/share
│   └── wardrobe/
│       └── [id].tsx            # Item detail with wardrobe matches
├── components/                 # Reusable UI components
│   ├── ImageEditor.tsx         # Crop/rotate editor with draggable handles
│   ├── PhotoGuideExamples.tsx  # Do/Don't photo tips for body photos
│   ├── SilhouetteOverlay.tsx   # Body outline SVG overlay on camera
│   └── TryOnUsageBadge.tsx     # Daily try-on usage counter pill
├── config/
│   └── api.ts                  # Platform-specific backend URL configuration
├── lib/                        # Shared utilities & API client
│   ├── api.ts                  # Central HTTP client — all API endpoints
│   ├── constants.ts            # DEMO_USER_ID, validation thresholds
│   ├── icons.tsx               # Lucide icon barrel export
│   ├── imageValidation.ts      # Client-side blur/brightness/body detection
│   └── onboarding/             # Body type questionnaire helpers
│       ├── bodyShapeIcons.tsx  # SVG body shape icons
│       └── scoreBodyType.ts    # Algorithmic body type scoring
├── theme/
│   └── tokens.ts               # Design system (colors, spacing, typography)
├── onboarding.tsx              # Onboarding questionnaire screen
├── style-match.tsx             # Style match analysis screen
├── assets/                     # App icons, images
├── package.json                # Dependencies
├── app.json                    # Expo configuration
├── tsconfig.json               # TypeScript configuration
└── babel.config.js             # Babel configuration
```

### Backend (`/server`)

```
server/
├── app/                        # Main application package
│   ├── __init__.py
│   ├── main.py                 # FastAPI entry point, middleware, routers, cleanup
│   ├── database.py             # SQLAlchemy engine + session (SQLite)
│   ├── models.py               # ORM models (User, ClothingItem, CalendarEntry, etc.)
│   ├── schemas.py              # Pydantic request/response models
│   ├── config.py               # Body-type rule loading from YAML
│   ├── pairing_engine.py       # Core outfit scoring (7-signal blend)
│   ├── style_embeddings.py     # FashionCLIP: embedding, zero-shot, gender
│   ├── style_advisor.py        # Gemini AI outfit explanations
│   ├── style_match.py          # Single-item match analysis engine
│   ├── matching_service.py     # Wardrobe match + shopping link generation
│   ├── shopping_service.py     # Multi-provider shopping search
│   ├── shopping_links.py       # Google Shopping & Meesho URL builders
│   ├── try_on_service.py       # Virtual try-on with 5 providers
│   ├── recommender.py          # LightFM collaborative filtering
│   ├── learned_compatibility.py # Optional outfit-transformer scoring
│   ├── celery_app.py           # Celery + Redis configuration
│   ├── tasks.py                # Celery tasks (async try-on rendering)
│   ├── storage.py              # Local/S3/GCS file storage abstraction
│   ├── retry.py                # HTTP retry with exponential backoff
│   └── routers/                # API route handlers
│       ├── clothing.py         # CRUD for clothing items + suggestions
│       ├── users.py            # User management, body type, consent, photo
│       ├── upload.py           # Image upload endpoint
│       ├── tagging.py          # AI auto-tagging (FashionCLIP or Gemini)
│       ├── outfits.py          # Outfit suggestions + feedback
│       ├── calendar.py         # Calendar entry management
│       ├── shopping.py         # Wardrobe gap detection + product search
│       ├── shop_matches.py     # Per-item shopping matches
│       ├── style_advice.py     # AI style advice with shopping
│       ├── style_match.py      # Style match analysis
│       ├── tryon.py            # Virtual try-on job management
│       └── wardrobe.py         # Wardrobe CRUD (legacy)
├── config/
│   └── body_type_rules.yaml    # Body type → style tag boost mappings
├── models/
│   └── recommender.pkl         # Serialized LightFM model
├── scripts/                    # Utility scripts
│   ├── init_db.py              # Create all database tables
│   ├── seed_db.py              # Seed demo user + sample items
│   ├── eval_pairing.py         # Pairing engine evaluation script
│   ├── retrain_recommender.py  # Retrain LightFM model
│   ├── migrate_add_columns.py  # Migration: granular clothing attributes
│   ├── migrate_add_consent.py  # Migration: photo consent columns
│   ├── migrate_body_type_rules.py  # Migration: body type + style tags
│   ├── migrate_embedding_column.py # Migration: FashionCLIP embeddings
│   ├── migrate_target_gender.py    # Migration: gender targeting
│   └── migrate_tryon_usage.py      # Migration: try-on rate limiting table
├── tests/                      # Unit and integration tests
│   ├── test_pairing_engine.py  # Color harmony, outfit scoring, HSL helpers
│   ├── test_body_type.py       # Body type API endpoint tests
│   ├── test_classification_regression.py  # FashionCLIP regression tests
│   ├── test_retry.py           # HTTP retry exponential backoff tests
│   ├── test_shop_matches.py    # Shopping match endpoint tests
│   └── test_style_embeddings.py # Embedding + cosine similarity tests
├── third_party/
│   └── outfit-transformer/     # Optional: pretrained outfit compatibility model
├── uploads/                    # Uploaded images (gitignored)
├── stylemate.db                # SQLite database (gitignored)
├── venv/                       # Python virtual environment (gitignored)
├── .env                        # Environment variables (gitignored)
├── requirements.txt            # Python dependencies
└── PROJECT_CONTEXT.md          # Server-specific context
```

---

## Project Flow

### Flow 1: Adding a Clothing Item

```
User taps "Add Item" tab
    │
    ▼
Frontend: /app/(tabs)/add-item.tsx renders
    │
    ▼
User taps "Take Photo" → navigates to /app/capture.tsx
    │
    ▼
Camera captures image → ImageEditor (crop/rotate) → ImageValidation (blur/brightness/body check)
    │
    ▼
Frontend: POST /upload-image (multipart file)
    │
    ▼
Backend: /upload.py → storage.get_storage_provider() saves file locally/S3/GCS
    │
    ▼
Returns: { image_url: "/uploads/abc.jpg" }
    │
    ▼
Frontend: POST /tag-item { image_url }
    │
    ▼
Backend: /tagging.py → FashionCLIP zero-shot classification
    │
    ▼
Returns: { category: "top", dominant_color: "navy", pattern: "solid",
           occasion_tag: "office", season: "all-season", fabric_type: "cotton",
           fit_type: "slim", target_gender: "men", formality_score: 3,
           style_tags: ["structured"], _needs_review: ["fabric_type"] }
    │
    ▼
Frontend: Populates editable form (yellow-highlighted = needs review)
    │
    ▼
User confirms/edits tags → taps "Save"
    │
    ▼
Frontend: POST /clothing { user_id, image_url, category, color, ... }
    │
    ▼
Backend: Saves to SQLite → spawns background thread for FashionCLIP embedding
    │
    ▼
Frontend: router.replace("/wardrobe") → item appears in grid
```

### Flow 2: Getting Outfit Suggestions

```
User taps "Outfits" tab
    │
    ▼
Frontend: GET /outfit-suggestions?user_id=1&limit=5
    │
    ▼
Backend: pairing_engine.suggest_outfits()
    │
    ├─ 1. Load all user's ClothingItems from DB
    ├─ 2. Group by category (top, bottom, footwear, outerwear, dress, accessory)
    ├─ 3. Generate valid combinations (top+bottom+shoes, dress+shoes, etc.)
    ├─ 4. For each pair, compute blended score:
    │      ├── 35% Color harmony (HSL-based: analogous/complementary/clashing)
    │      ├── 25% FashionCLIP embedding cosine similarity
    │      ├── 15% Hard rules (occasion, formality, gender compatibility)
    │      ├── 10% Fabric compatibility
    │      ├── 8%  Fit contrast (slim+oversized=good)
    │      ├── 7%  Season match
    │      └── 7%  Style tag compatibility
    ├─ 5. Apply body-type boost (from body_type_rules.yaml)
    ├─ 6. Blend LightFM ML prediction (adaptive weight based on feedback count)
    ├─ 7. Apply busy-pattern penalty (-50%) and complementary palette bonus (+10%)
    └─ 8. Return top 5 scored outfits with reasons
    │
    ▼
Returns: [{ items: [...], score: 0.87, reason: "Classic navy and white...", breakdown: {...} }]
    │
    ▼
Frontend: Renders cards with thumbnails, score badges, breakdown bars
    │
    ├─ User likes/dislikes → POST /outfit-feedback → retrains LightFM
    └─ User taps "Try It On" → POST /try-on → Celery job → Poll for result
```

### Flow 3: Virtual Try-On

```
User taps "Try It On" on an outfit suggestion
    │
    ▼
Frontend: POST /try-on { garment_ids: [3, 7, 12] }
    │
    ▼
Backend: /tryon.py
    ├─ Check rate limit (5/day per user)
    ├─ Validate photo consent
    ├─ Validate garment ownership
    ├─ Create TryOnResult record (status: "processing")
    └─ Spawn Celery task (or inline thread fallback)
    │
    ▼
Celery: tasks.execute_tryon_job()
    │
    ▼
try_on_service.render_outfit():
    ├─ Hash photo + garment URLs for cache key
    ├─ Check TTLCache (7-day TTL)
    ├─ Map categories: top→upper_body, bottom→lower_body, dress→dresses
    ├─ For dress: single pass; for top+bottom: sequential passes
    └─ Call provider (FAL.ai default) with user photo + garment image
    │
    ▼
Provider returns rendered image URL → saved to TryOnResult
    │
    ▼
Frontend: Polls GET /try-on/{job_id} every 2 seconds
    │
    ▼
When status="completed" → navigates to /try-on.tsx → displays result with Save/Share
```

### Flow 4: Style Match

```
User views item detail → taps "Style Match Suggestions"
    │
    ▼
Frontend: GET /style-match?item_id=42
    │
    ▼
Backend: style_match.generate_style_match()
    ├─ Load selected item
    ├─ Find complementary items from wardrobe (by category mapping)
    ├─ Score each by color harmony (HSL complementary/analogous/triadic)
    ├─ Generate named purchase suggestions for missing categories
    ├─ Compute recommended/avoid colors using color theory
    ├─ Map occasion-based outfit ideas
    └─ Build shopping links (Google Shopping, Meesho)
    │
    ▼
Returns: { selected_item, matching_bottoms/tops/footwear, recommended_colors,
           avoid_colors, occasion_outfits, shopping_suggestions }
    │
    ▼
Frontend: Renders sections with match cards, color chips, product cards
```

---

## API Documentation

### Base URL

- **Local:** `http://127.0.0.1:8000`
- **Swagger docs:** `http://127.0.0.1:8000/docs`

### Users

| Method | Endpoint | Request | Response | Description |
|--------|----------|---------|----------|-------------|
| GET | `/users/` | — | `list[UserResponse]` | List all users |
| POST | `/users/` | `UserCreate` body | `UserResponse` (201) | Create user |
| GET | `/users/{id}` | header: X-User-ID | `UserResponse` | Get user profile |
| POST | `/users/{id}/body-type` | `BodyTypeIn` { body_type } | `UserResponse` | Set body type |
| GET | `/users/{id}/consent` | header: X-User-ID | `ConsentResponse` | Get consent status |
| POST | `/users/{id}/consent` | `ConsentIn` { agreed, version } | `ConsentResponse` | Give photo consent |
| PUT | `/users/{id}/photo` | `PhotoUrlIn` { photo_url } | `UserResponse` | Set body photo |
| DELETE | `/users/{id}/photo` | header: X-User-ID | 204 | Delete body photo + try-on results |

### Clothing Items

| Method | Endpoint | Request | Response | Description |
|--------|----------|---------|----------|-------------|
| GET | `/clothing/` | query: user_id, category, season, occasion_tag, target_gender | `list[ClothingItemResponse]` | List items with filters |
| POST | `/clothing/` | `ClothingItemCreate` body | `ClothingItemResponse` (201) | Create item + background embedding |
| GET | `/clothing/{id}` | — | `ClothingItemResponse` | Get single item |
| PUT | `/clothing/{id}` | `ClothingItemUpdate` body | `ClothingItemResponse` | Update item |
| DELETE | `/clothing/{id}` | — | `{"detail": "Item deleted"}` | Delete item |
| GET | `/clothing/{id}/suggestions` | query: category, limit | match results | Get item suggestions by category |
| GET | `/clothing/{id}/complete-outfit` | — | outfit completion | Complete the outfit for one item |

### Upload & Tagging

| Method | Endpoint | Request | Response | Description |
|--------|----------|---------|----------|-------------|
| POST | `/upload-image` | multipart `UploadFile` | `{ image_url }` | Upload image file (JPEG/PNG/GIF/WebP/HEIC, max 10MB) |
| POST | `/tag-item` | `{ image_url }` | tags dict with `_confidence`, `_needs_review` | AI auto-tag clothing item |

### Outfit Suggestions

| Method | Endpoint | Request | Response | Description |
|--------|----------|---------|----------|-------------|
| GET | `/outfit-suggestions` | query: user_id, occasion_tag, target_gender, limit | `list[OutfitSuggestionResponse]` | Get scored outfit suggestions |
| POST | `/outfit-feedback` | `OutfitFeedbackIn` { outfit_item_ids, liked } | `OutfitFeedbackResponse` | Submit like/dislike feedback |

### Calendar

| Method | Endpoint | Request | Response | Description |
|--------|----------|---------|----------|-------------|
| POST | `/calendar-entries/` | `CalendarEntryCreate` body | `CalendarEntryResponse` (201) | Create calendar entry |
| GET | `/calendar-entries/` | query: user_id, start_date, end_date | `list[CalendarEntryResponse]` | List entries |
| PATCH | `/calendar-entries/{id}` | `CalendarEntryUpdate` body | `CalendarEntryResponse` | Update entry (lock outfit) |

### Shopping

| Method | Endpoint | Request | Response | Description |
|--------|----------|---------|----------|-------------|
| GET | `/shopping-suggestions` | query: user_id, target_gender, occasion_tag | `list[ShoppingGroupResponse]` | Wardrobe gap detection + product search |
| GET | `/items/{id}/shop-matches` | query: refresh | product groups | Shopping matches for specific item |

### Style

| Method | Endpoint | Request | Response | Description |
|--------|----------|---------|----------|-------------|
| GET | `/style-match` | query: item_id | style match dict | Full style-match analysis for one item |
| GET | `/style-advice` | query: item_id | `StyleAdviceResponse` | AI style advice with shopping links |

### Virtual Try-On

| Method | Endpoint | Request | Response | Description |
|--------|----------|---------|----------|-------------|
| GET | `/try-on/usage/{user_id}` | — | `TryOnUsageOut` | Check daily try-on usage |
| POST | `/try-on` | `TryOnRenderIn` { garment_ids } | `TryOnJobOut` (202) | Submit try-on job |
| GET | `/try-on/{job_id}` | — | `TryOnResultOut` | Poll job status |
| GET | `/try-on/results/{user_id}` | — | `list[TryOnResultOut]` | List all try-on results |

---

## AI Workflow

### FashionCLIP (Primary Tagging & Embeddings)

**Model:** `patrickjohncyh/fashion-clip` from HuggingFace (~500MB)

**Why FashionCLIP:** Free, open-source, specifically trained on fashion data. Runs locally on CPU. No paid API needed.

**Used for:**
1. **Zero-shot image tagging** — Classifies category, color, pattern, occasion, season, fabric, fit, formality, gender
2. **Style embeddings** — 512-dimensional vectors stored per item for similarity scoring
3. **Visual similarity ranking** — Ranks shopping products by visual fit to a reference item
4. **Gender classification** — Dedicated classification with ambiguity handling

**Input:** Image file path or URL
**Output:** Embedding vector (512 floats) or classification labels with confidence scores

**Pipeline:**
```
Image → FashionCLIP vision encoder → normalized embedding (512-d)
                                         │
                                         ├── Cosine similarity with other embeddings
                                         ├── Zero-shot: compare with text label embeddings
                                         └── Gender: compare with men/women/unisex phrases
```

### Gemini API (Optional Tagging + Style Advice)

**Model:** `gemini-3.1-flash-lite` (configurable via `GEMINI_MODEL`)

**Used for:**
1. **Alternative tagging** — When `TAGGING_PROVIDER=vision_api`, sends base64 image to Gemini
2. **Style advice** — Generates shoe/accessory/layering recommendations for a single item
3. **Outfit explanations** — (Planned) Natural-language "why this works" explanations
4. **Query polishing** — (Optional) Polishes shopping search queries

### LightFM (Collaborative Filtering)

**What:** Learns from user like/dislike feedback to improve future suggestions.

**Pipeline:**
```
User likes/dislikes outfit suggestions
    │
    ▼
OutfitFeedback records accumulate in database
    │
    ▼
recommender.train_model() builds interaction matrix:
    - Users × Outfit combinations (sparse)
    - Item features: category, color, pattern, occasion, season, formality, style_tags
    │
    ▼
LightFM (warp loss, 30 components) trains model
    │
    ▼
Serialized to models/recommender.pkl
    │
    ▼
pairing_engine blends ML score (0-30% weight based on feedback count)
```

**Adaptive blending:** 0% ML weight with <10 feedbacks, ramps to 30% at 40+ feedbacks.

### Color Harmony Engine

**Algorithm:** HSL-based color theory scoring (built into `pairing_engine.py`)

```
Hex/RGB color → HSL conversion
    │
    ├── Low saturation (< 15%) → neutral → safe with anything (score 0.9)
    ├── Hue diff < 15° → analogous → high score (0.85)
    ├── Hue diff ~180° → complementary → high score (0.9)
    ├── Hue diff 90-150° or 210-270° → clashing → low score (0.3)
    └── Known fashion clashes (red+green, lime+purple) → penalty (0.15)
```

### Virtual Try-On Providers

| Provider | How It Works | When To Use |
|----------|-------------|-------------|
| **FAL.ai** (default) | Hosted IDM-VTON endpoint | Production — fast, reliable |
| **Fashn.ai** | Submit + poll API | Alternative hosted provider |
| **Kling** | Submit + poll API | Alternative hosted provider |
| **Self-hosted** | IDM-VTON/CatVTON on your own GPU | Full control, no API costs |
| **Free HF Space** | Public HuggingFace Gradio Space | Free, slower, cold starts |

**Multi-pass rendering:** For top+bottom+outerwear outfits, each garment is rendered sequentially — the result of one pass becomes the input for the next.

---

## Database Design

### Tables

```
┌──────────────┐       ┌──────────────────┐       ┌─────────────────┐
│    users      │       │  clothing_items   │       │ calendar_entries │
├──────────────┤       ├──────────────────┤       ├─────────────────┤
│ id (PK)      │◄──┐   │ id (PK)          │       │ id (PK)         │
│ name         │   │   │ user_id (FK) ────┼───────┤ user_id (FK)    │
│ email        │   │   │ image_url        │       │ date            │
│ gender       │   │   │ category         │       │ occasion_tag    │
│ target_gender│   │   │ color            │       │ locked_outfit_id│
│ style_pref   │   │   │ pattern          │       │ created_at      │
│ body_type    │   │   │ occasion_tag     │       └─────────────────┘
│ photo_consent│   │   │ season           │
│ consent_at   │   │   │ brand            │       ┌─────────────────┐
│ consent_ver  │   │   │ name             │       │ try_on_results   │
│ photo_url    │   │   │ formality        │       ├─────────────────┤
│ photo_key    │   │   │ target_gender    │       │ id (PK)         │
│ last_active  │   │   │ fabric_type      │       │ job_id (UUID)   │
│ created_at   │   │   │ fit_type         │       │ user_id (FK) ───┼──┐
└──────────────┘   │   │ sleeve_length    │       │ status          │  │
                   │   │ formality_score  │       │ outfit_items_json│  │
                   │   │ tags             │       │ result_image_url│  │
                   │   │ style_tags       │       │ error_message   │  │
                   │   │ embedding_json   │       │ error_type      │  │
                   │   │ created_at       │       │ model_used      │  │
                   │   │ updated_at       │       │ latency_ms      │  │
                   │   └──────────────────┘       │ created_at      │  │
                   │                              └─────────────────┘  │
                   │   ┌──────────────────┐       ┌─────────────────┐  │
                   │   │ outfit_feedback   │       │ try_on_usage    │  │
                   │   ├──────────────────┤       ├─────────────────┤  │
                   │   │ id (PK)          │       │ id (PK)         │  │
                   └───┤ user_id (FK)     │       │ user_id (FK) ───┼──┘
                       │ outfit_item_ids  │       │ usage_date      │
                       │ liked (0/1)      │       │ count           │
                       │ created_at       │       │ updated_at      │
                       └──────────────────┘       └─────────────────┘
```

### Key Relationships

- **User → ClothingItem:** One-to-many (a user owns many items)
- **User → CalendarEntry:** One-to-many (a user has many calendar entries)
- **User → TryOnResult:** One-to-many (a user has many try-on results)
- **User → OutfitFeedback:** One-to-many (a user gives many feedbacks)
- **User → TryOnUsage:** One-to-many (one record per user per day)
- **ClothingItem → CalendarEntry:** Via `locked_outfit_id` (stores comma-separated item IDs)

### Key Fields

- **ClothingItem.embedding_json:** Stores FashionCLIP 512-d embedding as JSON array for similarity search
- **ClothingItem.style_tags:** Comma-separated AI-detected style tags (e.g., "structured,belted,wrap_style")
- **TryOnResult.job_id:** UUID used for polling job status from frontend
- **OutfitFeedback.outfit_item_ids:** Comma-separated item IDs representing the outfit

---

## State Management

**Approach:** React hooks (`useState`, `useEffect`, `useCallback`, `useMemo`) — no external state library.

**Why:** The app is relatively simple with isolated screens. Each screen fetches its own data on mount/focus. No cross-screen shared state beyond what the API provides.

**Pattern:**
```typescript
// Each screen follows this pattern:
const [data, setData] = useState([]);
const [loading, setLoading] = useState(true);

const loadData = useCallback(async () => {
  setLoading(true);
  const result = await someApi.fetch();
  setData(result);
  setLoading(false);
}, []);

useFocusEffect(useCallback(() => { loadData(); }, [loadData]));
```

**Exceptions:**
- `AsyncStorage` — stores `onboarding_complete` flag locally
- `useRef` — stores interval IDs for try-on polling (cleanup on unmount)

---

## Authentication & Privacy

### Current Auth Model

**Single-user demo mode** — hardcoded `DEMO_USER_ID = 1`. No login/signup flow. No JWT/OAuth.

### Privacy & Consent Flow

1. **Consent screen** (`/consent`) — User must explicitly agree before uploading body photos
2. **Consent record** — Stored in `users` table with version and timestamp
3. **Photo storage** — Body photos stored separately from item photos
4. **Photo deletion** — User can delete their photo anytime from Settings
5. **Photo retention** — Background thread deletes photos of inactive users after 90 days
6. **Account deletion** — `DELETE /users/{id}` cascades: deletes user, all items, all photos, all try-on results

### Privacy Policy

Built-in privacy policy screen (`/privacy`) explaining:
- What photos are collected and why
- What photos are NOT used for
- Data retention period (90 days)
- User rights (access, deletion)

---

## Error Handling

### Frontend

- **API errors:** Centralized `apiFetch` function catches HTTP errors and shows toast messages
- **Image validation:** Client-side checks for blur (Laplacian variance), brightness, minimum size, body detection
- **Try-on errors:** Structured error types: `bad_photo` (suggests retake), `rate_limit` (shows reset time), `provider_error` (retry), generic failure
- **Loading states:** Every data-fetching screen has loading spinner, empty state, and error state

### Backend

- **Validation:** Pydantic models validate all request/response data
- **AI failures:** If FashionCLIP/Gemini fails, returns fallback "unclassified" tags instead of crashing
- **Retry logic:** `retry.py` implements exponential backoff for HTTP 429/5xx errors (2^attempt seconds, max 3 retries)
- **Try-on errors:** Typed error hierarchy (`TryOnInputError`, `TryOnAuthError`, `TryOnTimeoutError`, `TryOnProviderDownError`, `TryOnRateLimitError`) with appropriate HTTP status codes
- **Shopping faults:** `asyncio.gather` with `return_exceptions=True` — if one shopping provider fails, others still return results

---

## Performance

### Caching

- **FashionCLIP embeddings:** Computed once per item, stored in `embedding_json` column
- **Try-on results:** In-memory TTLCache keyed by `{photo_hash}:{garment_url}`, 7-day TTL
- **Shop matches:** TTLCache (500 entries, 30min) per item_id
- **Style advice:** TTLCache (200 entries, 30min) per item_id
- **Shopping providers:** Flipkart results cached (500 entries, 30min)

### Optimizations

- **Lazy loading:** FashionCLIP model loaded on first use, not at startup
- **Background threads:** Embedding computation happens in background threads after item creation
- **Async shopping:** Concurrent `asyncio.gather` for multi-provider product search
- **Client-side filtering:** Wardrobe filters (category, occasion, gender, search) computed via `useMemo`
- **Image preprocessing:** Photos resized/compressed client-side before upload

---

## Security

- **Consent gating:** Body photo upload requires explicit GDPR-style consent
- **Owner authorization:** User endpoints check `X-User-ID` header matches resource owner
- **File validation:** Upload endpoint validates file type (JPEG/PNG/GIF/WebP/HEIC) and size (max 10MB)
- **Rate limiting:** Virtual try-on limited to 5 per day per user
- **Photo cleanup:** Inactive user photos auto-deleted after 90 days
- **Environment variables:** All API keys stored in `.env` (gitignored), never hardcoded
- **No auth tokens:** Single-user demo mode (no JWT/OAuth yet)

---

## Setup Instructions

### Prerequisites

- [Node.js](https://nodejs.org) 18+ (LTS)
- Python 3.9+
- [Expo Go](https://expo.dev/go) app on your phone (or iOS/Android simulator)
- Redis (for Celery async tasks — optional for basic features)

### Backend Setup

```bash
cd server

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create tables + seed demo data
python scripts/init_db.py
python scripts/seed_db.py

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup

```bash
cd app

# Install dependencies
npm install

# Start the Expo dev server
npm start
```

- **On your phone:** Open Expo Go and scan the QR code
- **iOS simulator:** Press `i` in the terminal (macOS + Xcode required)
- **Android emulator:** Press `a` in the terminal (Android Studio required)
- **Web browser:** Press `w` in the terminal

### Connect Frontend to Backend

Update `app/config/api.ts` with your machine's LAN IP:

```typescript
android: "http://YOUR_LAN_IP:8000",
```

Find your LAN IP:
```bash
ip addr show | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}' | cut -d/ -f1
```

- **Physical device (Expo Go):** Use LAN IP. Phone and computer must be on the same Wi-Fi.
- **Android emulator:** `http://10.0.2.2:8000` works by default.
- **iOS simulator:** `http://127.0.0.1:8000` works by default.

---

## Environment Variables

Create a `.env` file in `server/`:

```env
# === Tagging ===
TAGGING_PROVIDER=fashion_clip          # "fashion_clip" (local) or "vision_api" (Gemini)
GEMINI_API_KEY=your_gemini_key         # Only needed if TAGGING_PROVIDER=vision_api
GEMINI_MODEL=gemini-3.1-flash-lite

# === Shopping ===
SHOPPING_PROVIDERS=flipkart,meesho     # Comma-separated: flipkart, meesho, amazon
FLIPKART_AFFILIATE_ID=your_id
FLIPKART_AFFILIATE_TOKEN=your_token
AMAZON_AFFILIATE_TAG=your_tag
MEESHO_SEARCH_URL=https://www.meesho.com/search?q=

# === Virtual Try-On ===
TRYON_PROVIDER=fal                     # fal | fashn | kling | self_hosted | free_hf_space
TRYON_DAILY_LIMIT=5
FAL_KEY=your_fal_key
TRYON_FASHN_API_KEY=your_fashn_key
TRYON_KLING_API_KEY=your_kling_key
FREE_PROVIDER_SPACE_ID=your_hf_space
HF_TOKEN=your_huggingface_token
TRYON_CACHE_TTL_SECONDS=604800         # 7 days

# === Storage ===
STORAGE_PROVIDER=local                 # local | s3 | gcs
S3_BUCKET=stylemate-photos
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
GCS_BUCKET=stylemate-photos

# === Background Tasks ===
REDIS_URL=redis://localhost:6379/0

# === Photo Lifecycle ===
PHOTO_RETENTION_DAYS=90
PHOTO_CLEANUP_INTERVAL_SECONDS=86400

# === ML ===
USE_LEARNED_COMPATIBILITY=false        # Enable outfit-transformer (optional, needs GPU)
AI_QUERY_POLISH=false                  # Use Gemini to polish shopping queries
```

---

## Running the Project

### Development Mode

```bash
# Terminal 1: Backend
cd server
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend
cd app
npm start

# Terminal 3 (optional): Celery worker for async try-on
cd server
source venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

### Available Endpoints

- **API docs:** http://127.0.0.1:8000/docs (Swagger UI)
- **Health check:** http://127.0.0.1:8000/health
- **Uploaded images:** http://127.0.0.1:8000/uploads/

---

## Testing

```bash
cd server
source venv/bin/activate

# Run all tests
pytest

# Run specific test files
pytest tests/test_pairing_engine.py      # Color harmony + scoring
pytest tests/test_body_type.py           # Body type API
pytest tests/test_retry.py              # HTTP retry logic
pytest tests/test_shop_matches.py       # Shopping matches
pytest tests/test_style_embeddings.py   # FashionCLIP embeddings
pytest tests/test_classification_regression.py  # Classification regression

# Evaluate pairing engine quality
python scripts/eval_pairing.py

# Retrain recommender model
python scripts/retrain_recommender.py
```

---

## Future Improvements

### Planned (from PROJECT_CONTEXT.md)

| Phase | Feature | Status |
|-------|---------|--------|
| Phase 2 | Wardrobe scanning + AI tagging | In progress (FashionCLIP integration) |
| Phase 3 | AI outfit suggestions | Implemented |
| Phase 4 | Calendar + occasion planning | Implemented |
| Phase 5 | Body type personalization | Implemented |
| Phase 6 | Shopping suggestions | Implemented |
| Phase 7 | Virtual try-on | Implemented |

### Potential Enhancements

- **Multi-user authentication** — JWT/OAuth login system
- **Weather-based recommendations** — OpenWeatherMap integration
- **AI packing assistant** — Trip-based wardrobe planning
- **Capsule wardrobe builder** — Algorithm to select optimal N items
- **AI fashion rating** — Selfie analysis with Gemini Vision
- **Outfit calendar enhancements** — Wear-frequency analytics, repeat prevention
- **PostgreSQL migration** — For production multi-user deployment
- **Docker deployment** — Containerized backend + frontend builds
- **CI/CD pipeline** — GitHub Actions for automated testing and deployment

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Frontend can't connect to backend | Check LAN IP in `app/config/api.ts`, ensure same Wi-Fi network |
| FashionCLIP slow on first load | Model downloads ~500MB on first use; subsequent loads are faster |
| Virtual try-on fails | Check `TRYON_PROVIDER` env var and API key; try `free_hf_space` for free option |
| Database not found | Run `python scripts/init_db.py && python scripts/seed_db.py` |
| Redis connection error | Celery tasks won't run without Redis; basic features still work |
| Upload fails | Check file type (JPEG/PNG/WebP/HEIC) and size (<10MB) |
| Camera not working | Grant camera permission in phone settings; check Expo Go permissions |
| Embedding not computed | Check background thread logs; embeddings compute after item creation |

---

## Frequently Asked Questions

**Q: Does this require a GPU?**
A: No. FashionCLIP runs on CPU (~2-5s per image). Virtual try-on uses cloud providers (FAL.ai default). GPU only needed for the optional outfit-transformer model.

**Q: Can I use this without API keys?**
A: Yes. Set `TAGGING_PROVIDER=fashion_clip` for free local tagging. Set `TRYON_PROVIDER=free_hf_space` for free virtual try-on. Shopping works with search link generation (no API keys needed for Meesho/Amazon).

**Q: How does the app know my body type?**
A: Through a 4-question onboarding questionnaire (shoulder/hip balance, waist definition, weight carry, silhouette match). The algorithm scores answers and assigns one of 5 body types: rectangle, hourglass, pear, apple, inverted_triangle.

**Q: How accurate are the outfit suggestions?**
A: The scoring engine blends 7 signals (color harmony, style embeddings, hard rules, fabric, fit, season, style tags). Accuracy improves with more wardrobe items and feedback. The LightFM model learns your preferences over time.

**Q: Is my body photo stored securely?**
A: Body photos require explicit GDPR-style consent. They're stored locally (or S3/GCS in production) and auto-deleted after 90 days of inactivity. You can delete your photo anytime from Settings.

**Q: How many virtual try-ons can I do per day?**
A: Default limit is 5 per day (configurable via `TRYON_DAILY_LIMIT`). The counter resets at midnight.

**Q: Can I run this on a single machine?**
A: Yes. The minimum setup is just the FastAPI server + Expo app. Redis/Celery are optional (try-on falls back to inline threading without them).
