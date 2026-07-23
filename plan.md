# StyleMate — Project Plan & Progress

## Completed Work (beyond original prompts)

### Infrastructure & Code Quality
- **Design token system** — `app/theme/tokens.ts` with shared `spacing`, `fontSize`, `fontWeight`, `borderRadius`, `colors`, `shadow` — refactored across all 16+ screens.
- **Safe area** — `SafeAreaProvider`/`SafeAreaView` applied to all screens.
- **Lucide icon migration** — Replaced all unicode/emoji icons with `lucide-react-native` via a barrel export (`app/lib/icons.tsx`).
- **TypeScript** — Project compiles with zero TS errors.

### Features Implemented
- Wardrobe CRUD, AI tagging, outfit suggestions (pairing engine with color theory + FashionCLIP embeddings + ML blending).
- Calendar with occasion planning and outfit locking.
- Body type onboarding questionnaire with style-tag bias in scoring.
- Like/dislike feedback loop with LightFM ML integration.
- Virtual try-on via async job system (Celery + HF Space or local Gradio).
- Shopping suggestions with gap detection and multi-store links (Meesho, Myntra, Ajio, Amazon, Flipkart, Google Shopping).
- Style match — per-item compatibility scoring across all partner categories.
- Complete outfit — given one item, finds the complementary category match.
- **Image crop & rotate editor** — `app/components/ImageEditor.tsx` with draggable crop handles and 90° rotation, integrated into photo capture flow.
- **Wardrobe match suggestions** — detail page shows complementary items from own wardrobe, scored by color harmony.

### Current Known Issues (to fix)
- (none — all identified issues have been resolved)

---

## Improvement Plan

### Phase 1 — Fix & Cleanup ✅
- [x] Front camera for body selfies (`capture.tsx:183`)
- [x] Fix calendar lock bug (pass real outfit ID)
- [x] Clean up code smells (deduplicate `DEMO_USER_ID`, fix consent navigation)
- [x] Delete dead duplicate screens (`app/app/onboarding.tsx`, `app/app/style-match.tsx`)

### Phase 2 — Feature Additions ✅
- [x] Settings navigation entry (gear icon in header)
- [x] Wardrobe search bar (text filter by name)
- [x] Wardrobe pull-to-refresh (`RefreshControl`)
- [x] Fix misleading empty state (distinguish API failure vs empty)
- [x] Fix add-item form reset (preserve state across navigations)

### Phase 3 — Home Screen Redesign ✅
- [x] Today's Outfit suggestion card
- [x] Wardrobe stats (item count by category)
- [x] Calendar preview (next locked/suggested outfit)

---

All planned improvements complete.

---

## Phase 4 — AI Feature Expansion

### Overview

Eight AI-powered features planned, leveraging existing Gemini integration (`style_advisor.py`), FashionCLIP embeddings (`style_embeddings.py`), and the blended scoring engine (`pairing_engine.py`). Ordered by effort (quick wins first).

| Tier | Feature | Effort | Depends On |
|------|---------|--------|------------|
| 1 | Closet Gap Analysis | ~1 file server, ~30 lines client | `find_gaps()` exists |
| 1 | AI Stylist (outfit explanations) | ~40 lines server, ~20 lines client | Gemini + pairing engine |
| 2 | Smart Outfit Generator | ~60 lines server + prompt, ~40 lines client | Tier 1b pattern |
| 2 | Weather-Based Recommendations | ~80 lines server, ~40 lines client | `WEATHER_API_KEY` |
| 2 | AI Packing Assistant | ~70 lines server, ~50 lines client | Gemini + wardrobe |
| 3 | Capsule Wardrobe Builder | ~120 lines server (algorithm), ~60 lines client | Pairing engine |
| 3 | AI Fashion Rating (selfie) | ~50 lines server, ~80 lines client | Gemini Vision |
| 3 | Outfit Calendar Enhancements | ~40 lines server, ~30 lines client | Calendar exists |

---

### Feature 4.1 — Closet Gap Analysis

**Goal:** Expose existing `find_gaps()` via endpoint + shopping links, show on home screen.

**Server:**
- File: `server/app/pairing_engine.py` — already done (`find_gaps()` at line 212)
- File: `server/app/routers/clothing.py` — add `GET /closet-gaps` endpoint:
  ```python
  @router.get("/closet-gaps")
  def get_closet_gaps(user_id: int = 1, db: Session = Depends(get_db)):
      gaps = find_gaps(user_id, db)
      results = []
      for gap in gaps:
          query = build_search_query(gap, db)
          results.append({
              "missing_category": gap.missing_category,
              "reason": gap.reason,
              "search_query": query,
          })
      return results
  ```
- File: `server/app/schemas.py` — add `ClosetGapResponse` pydantic model

**Client:**
- File: `app/lib/api.ts` — add `wardrobeApi.gaps()` method
- File: `app/app/(tabs)/index.tsx` — add "Closet Gaps" section below wardrobe stats:
  - `FlatList` of gap cards with category icon, reason text
  - When tapped: open shopping search for the gap category
  - Empty state: "Your wardrobe looks well-rounded!" if no gaps

---

### Feature 4.2 — AI Stylist (Outfit Explanations)

**Goal:** Given an outfit's item IDs, generate a natural-language "stylist" explanation of why they work together.

**Server:**
- File: `server/app/style_advisor.py` — add `explain_outfit()` function:
  ```python
  def explain_outfit(items: list[ClothingItem], db: Session) -> str:
      # Build item descriptions + pair scores
      # Call Gemini with stylist persona prompt
      # Return 2-3 conversational sentences
  ```
  Prompt: *"You are a professional stylist. These items are being worn together: {item_descriptions}. The color harmony score is {color_score}, fit contrast is {fit_score}, fabric affinity is {fabric_score}. Explain in 2-3 conversational sentences why this outfit works (or doesn't work). Be specific — mention colors, textures, silhouettes."*

- File: `server/app/routers/style_advice.py` — add `POST /explain-outfit` endpoint:
  ```python
  class ExplainOutfitIn(BaseModel):
      outfit_item_ids: list[int]
  
  @router.post("/explain-outfit")
  def explain_outfit_endpoint(payload: ExplainOutfitIn, db: Session = Depends(get_db)):
      items = db.query(ClothingItem).filter(ClothingItem.id.in_(payload.outfit_item_ids)).all()
      explanation = explain_outfit(items, db)
      return {"explanation": explanation}
  ```
- Cache results per `sorted(item_ids)` tuple for 30 min.

**Client:**
- File: `app/lib/api.ts` — add `styleAdviceApi.explain()` method
- File: `app/app/(tabs)/outfit-suggestions.tsx` — add expandable "Why this works" section on each suggestion card:
  - Collapsed state: small "Why this works?" text button
  - Tapped: calls API, shows explanation in expandable panel with a fade-in animation
  - Loading state: shimmer placeholder

---

### Feature 4.3 — Smart Outfit Generator

**Goal:** Accept natural language queries ("something for an interview", "beach wedding") and generate outfits with confidence badges.

**Server:**
- File: `server/app/services/nlp_router.py` — new module:
  ```python
  import json
  import httpx
  from app.routers.tagging import GEMINI_API_KEY, GEMINI_API_URL, GEMINI_MODEL
  
  def parse_query_to_params(query: str) -> dict:
      """Use Gemini to extract structured outfit params from a free-text query."""
      prompt = f"""Extract structured outfit parameters from this user request.
  Return ONLY valid JSON with NO markdown formatting.
  User request: "{query}"
  
  Fields:
  - occasion_tag: "casual" | "office" | "ethnic" | "party" | "formal" | "loungewear" | "travel" | null
  - formality_level: 1-5 integer (1=casual, 5=black tie) | null
  - season: "spring" | "summer" | "fall" | "winter" | "all-season" | null
  - target_gender: "men" | "women" | "unisex" | null
  - vibe: "minimal" | "colorful" | "classic" | "edgy" | "bohemian" | "sporty" | null
  
  If a field can't be inferred, set it to null. Do NOT guess.
  """
      # ... call Gemini API, parse response, return dict
  ```

- File: `server/app/routers/outfits.py` — add `POST /smart-outfit` endpoint:
  ```python
  class SmartOutfitIn(BaseModel):
      query: str
      limit: int = 5
  
  @router.post("/smart-outfit", response_model=list[OutfitSuggestionResponse])
  def smart_outfit(payload: SmartOutfitIn, db: Session = Depends(get_db)):
      params = parse_query_to_params(payload.query)
      results = suggest_outfits(db, user_id=1,
          occasion_tag=params.get("occasion_tag"),
          target_gender=params.get("target_gender"),
          limit=payload.limit,
      )
      # Add confidence level based on how many params were inferred
      # ...
      return results
  ```

**Client:**
- File: `app/lib/api.ts` — add `outfitApi.smartSuggest()` method
- File: `app/app/(tabs)/outfit-suggestions.tsx` — add text input at top:
  - Placeholder: "Describe what you need... (e.g. 'interview tomorrow')"
  - "Generate" button next to input
  - Results shown as highlighted cards with confidence badge (e.g. "High confidence match")
  - Preserve existing tab-based filters as secondary

---

### Feature 4.4 — Weather-Based Recommendations

**Goal:** Fetch weather for user location, filter wardrobe by temp-appropriate items, suggest top outfit.

**Server:**
- File: `server/app/services/weather_service.py` — new module:
  ```python
  import httpx
  import os
  
  WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
  WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
  
  TEMP_RULES = {
      (35, 50): {"season": "summer", "fabrics": ["cotton", "linen", "silk"]},
      (20, 35): {"season": "spring", "fabrics": ["cotton", "denim", "knit"]},
      (10, 20): {"season": "fall", "fabrics": ["cotton", "wool", "denim"]},
      (-10, 10): {"season": "winter", "fabrics": ["wool", "leather", "knit"]},
  }
  
  def get_weather(city: str = "Mumbai") -> dict:
      # Call OpenWeatherMap, return temp_c, condition, humidity
      # ...
  
  def filter_items_by_weather(items: list, temp_c: float) -> list:
      # Match temp range → season/fabric filter
      # ...
  ```

- File: `server/app/routers/outfits.py` — add `GET /weather-outfit` endpoint:
  ```python
  @router.get("/weather-outfit", response_model=OutfitSuggestionResponse | None)
  def weather_outfit(city: str = "Mumbai", db: Session = Depends(get_db)):
      weather = get_weather(city)
      items = db.query(ClothingItem).filter(ClothingItem.user_id == 1).all()
      filtered = filter_items_by_weather(items, weather["temp_c"])
      # Run suggest_outfits on filtered subset
      # Return top result + weather info
  ```

**Client:**
- File: `app/lib/api.ts` — add `outfitApi.weatherSuggest()` method
- File: `app/app/(tabs)/index.tsx` — add weather widget:
  - Shows temperature + condition icon
  - "Today's Pick" outfit card below — tapping opens outfit detail
  - Uses device location (Expo Location) or default city
- File: `app/app.json` — add location permission strings

**Config:**
- Add `WEATHER_API_KEY` to `.env` + `server/app/config.py`

---

### Feature 4.5 — AI Packing Assistant

**Goal:** Given destination, duration, purpose → generate packing list from user's wardrobe + shopping links for missing items.

**Server:**
- File: `server/app/services/packing_service.py` — new module:
  ```python
  def generate_packing_list(destination: str, duration: int, purpose: str, user_id: int, db: Session) -> dict:
      # Gemini prompt: "For a {duration}-day trip to {destination} for {purpose},
      # list the ideal clothing items by category with quantities needed."
      # Match against user's wardrobe, find gaps
      # Return: { selected_items: [...], missing_groups: [...], shopping_links: {...} }
  ```

- File: `server/app/routers/packing.py` — new router:
  ```python
  router = APIRouter(prefix="/packing", tags=["packing"])
  
  class PackingRequest(BaseModel):
      destination: str
      duration: int
      purpose: str  # "leisure" | "business" | "beach" | "wedding" | "adventure"
  
  @router.post("/packing-list")
  def get_packing_list(req: PackingRequest, db: Session = Depends(get_db)):
      return generate_packing_list(req.destination, req.duration, req.purpose, 1, db)
  ```

- File: `server/app/main.py` — register `packing.router`

**Client:**
- File: `app/app/(tabs)/packing.tsx` — new screen:
  - Inputs: destination (text), duration (number picker), purpose (dropdown)
  - "Generate" button → calls API
  - Results: two sections:
    1. "From Your Wardrobe" — checklist of items with quantity needed, tap to check off
    2. "Items to Buy" — missing categories with shopping links
  - Save/share generated list

- File: `app/app/(tabs)/_layout.tsx` — add Packing tab (luggage icon)
- File: `app/lib/api.ts` — add `packingApi.generate()` method

---

### Feature 4.6 — Capsule Wardrobe Builder

**Goal:** Algorithm that selects N items from wardrobe maximizing total outfit combinations.

**Server:**
- File: `server/app/pairing_engine.py` — add `build_capsule()` function:
  ```python
  def build_capsule(user_id: int, target_count: int = 20,
                    occasion_filter: str | None = None,
                    db: Session | None = None) -> dict:
      # 1. Load user's items, optionally filtered by occasion
      # 2. Score every possible pair using existing score_pair()
      # 3. Greedy selection:
      #    a. Start with neutral core items (white/black/beige tops + bottoms)
      #    b. Iteratively add the item that creates the most NEW valid outfit combinations
      #    c. Track which pairs are already "covered"
      #    d. Stop when target_count reached no improvement possible
      # 4. Return: { items: [...], total_outfits: N, pair_count: N, categories: {...} }
  ```

- File: `server/app/routers/outfits.py` — add `POST /capsule-wardrobe` endpoint:
  ```python
  class CapsuleRequest(BaseModel):
      target_item_count: int = 20
      occasion_tag: str | None = None
  
  @router.post("/capsule-wardrobe")
  def capsule_wardrobe(req: CapsuleRequest, db: Session = Depends(get_db)):
      return build_capsule(1, target_count=req.target_item_count,
                          occasion_filter=req.occasion_tag, db=db)
  ```

**Client:**
- File: `app/app/(tabs)/capsule.tsx` — new screen:
  - Top: target count slider (10-40) with "M items → N outfits" live counter
  - Results grid: selected items grouped by category
  - Ability to tap an item to "lock" it (keep it in capsule)
  - "Regenerate" button
  - Stats card: total possible outfits, categories covered, most-used items

- File: `app/app/(tabs)/_layout.tsx` — add Capsule tab (diamond icon)
- File: `app/lib/api.ts` — add `outfitApi.buildCapsule()` method

---

### Feature 4.7 — AI Fashion Rating (Selfie Analysis)

**Goal:** Upload a full-body photo (reuse consent photo or new upload), get structured style rating from Gemini Vision.

**Server:**
- File: `server/app/services/fashion_rating_service.py` — new module:
  ```python
  def rate_outfit_photo(photo_url: str) -> dict:
      """Send photo to Gemini Vision, get structured fashion rating."""
      prompt = """Analyze this outfit photo as a professional fashion critic.
  Rate on a scale of 1-10 for each:
  - overall_style: overall visual appeal and coordination
  - color_harmony: how well colors work together
  - fit: how well clothes fit the wearer
  - occasion_match: suitability for the inferred context
  - silhouette_balance: proportions and visual weight
  
  Also suggest 3 specific, actionable improvements.
  Return ONLY valid JSON with NO markdown formatting:
  {
    "overall_style": {"score": 0-10, "reason": "..."},
    "color_harmony": {"score": 0-10, "reason": "..."},
    "fit": {"score": 0-10, "reason": "..."},
    "occasion_match": {"score": 0-10, "reason": "..."},
    "silhouette_balance": {"score": 0-10, "reason": "..."},
    "suggestions": ["...", "...", "..."],
    "vibe_tags": ["...", "..."],
    "primary_colors_detected": ["...", "..."]
  }
  """
      # Call Gemini Vision with photo URL + prompt
      # Parse JSON response
      # Return dict
  ```

- File: `server/app/routers/fashion_rating.py` — new router:
  ```python
  router = APIRouter(prefix="/fashion-rating", tags=["fashion-rating"])
  
  class RatingRequest(BaseModel):
      image_url: str
      user_id: int = 1
  
  @router.post("/rate")
  def rate_photo(req: RatingRequest):
      return rate_outfit_photo(req.image_url)
  ```

- File: `server/app/main.py` — register `fashion_rating.router`

**Client:**
- File: `app/app/(tabs)/style-rating.tsx` — new screen:
  - Shows user's existing consent photo or allows new upload
  - "Rate My Style" button → calls API with loading spinner
  - Results display:
    - Animated score ring (overall_style as primary number)
    - Sub-scores as progress bars (color_harmony, fit, etc.)
    - Suggestion chips — tapping a chip shows detailed explanation
    - Vibe tags as badges
  - "Rate Again" button

- File: `app/app/(tabs)/_layout.tsx` — add Style Rating tab (star icon)
- File: `app/lib/api.ts` — add `fashionRatingApi.rate()` method

---

### Feature 4.8 — Outfit Calendar Enhancements

**Goal:** Prevent repeat outfits within 30 days, show wear-frequency analytics, suggest diverse alternatives.

**Server:**
- New model field needed — verify if `OutfitFeedback` tracks liked outfits or just feedback. Use `CalendarEntry.locked_outfit_id` history to track what was worn when.
- File: `server/app/services/calendar_service.py` — new module:
  ```python
  def get_wear_frequency(user_id: int, item_id: int, db: Session) -> int:
      """Count how many times an item appears in locked calendar entries in last 30 days."""
  
  def get_item_wear_history(user_id: int, days: int = 30, db: Session = None) -> list[dict]:
      """Return all items locked in calendar grouped by count, for analytics."""
  ```

- File: `server/app/routers/calendar.py` — add new endpoints:
  ```python
  @router.get("/calendar/analytics")
  def calendar_analytics(user_id: int = 1, days: int = 30, db: Session = Depends(get_db)):
      return get_item_wear_history(user_id, days, db)
  
  @router.get("/calendar/repeat-check")
  def check_outfit_repeat(outfit_item_ids: str, db: Session = Depends(get_db)):
      # Comma-separated IDs
      # Check each item's wear frequency
      # Return warnings for items worn >3 times
  ```

**Client:**
- File: `app/app/(tabs)/calendar.tsx` — add wear-frequency warning:
  - When locking an outfit, check `/calendar/repeat-check`
  - If item worn ≥3 times in 30 days: show warning banner: "You've worn this top 4 times this month — try switching it up?"
  - Suggestion: "Try swapping this [top] with [alternative from wardrobe]"
  - (Alternative is a random unworn item from same category)

---

### Summary of All New Files

| Phase | New/Modified File | Change |
|-------|------------------|--------|
| 4.1 | `server/app/routers/clothing.py` | Add `GET /closet-gaps` endpoint |
| 4.1 | `server/app/schemas.py` | Add `ClosetGapResponse` |
| 4.1 | `app/lib/api.ts` | Add `wardrobeApi.gaps()` |
| 4.1 | `app/app/(tabs)/index.tsx` | Add Closet Gaps section |
| 4.2 | `server/app/style_advisor.py` | Add `explain_outfit()` |
| 4.2 | `server/app/routers/style_advice.py` | Add `POST /explain-outfit` |
| 4.2 | `app/lib/api.ts` | Add `styleAdviceApi.explain()` |
| 4.2 | `app/app/(tabs)/outfit-suggestions.tsx` | Add "Why this works" |
| 4.3 | `server/app/services/nlp_router.py` | New — NL→params parser |
| 4.3 | `server/app/routers/outfits.py` | Add `POST /smart-outfit` |
| 4.3 | `app/lib/api.ts` | Add `outfitApi.smartSuggest()` |
| 4.3 | `app/app/(tabs)/outfit-suggestions.tsx` | Add query input |
| 4.4 | `server/app/services/weather_service.py` | New — weather API |
| 4.4 | `server/app/routers/outfits.py` | Add `GET /weather-outfit` |
| 4.4 | `app/lib/api.ts` | Add `outfitApi.weatherSuggest()` |
| 4.4 | `app/app/(tabs)/index.tsx` | Add weather widget |
| 4.5 | `server/app/services/packing_service.py` | New — packing logic |
| 4.5 | `server/app/routers/packing.py` | New — packing endpoints |
| 4.5 | `server/app/main.py` | Register packing router |
| 4.5 | `app/app/(tabs)/packing.tsx` | New screen |
| 4.5 | `app/app/(tabs)/_layout.tsx` | Add Packing tab |
| 4.5 | `app/lib/api.ts` | Add `packingApi` |
| 4.6 | `server/app/pairing_engine.py` | Add `build_capsule()` |
| 4.6 | `server/app/routers/outfits.py` | Add `POST /capsule-wardrobe` |
| 4.6 | `app/app/(tabs)/capsule.tsx` | New screen |
| 4.6 | `app/app/(tabs)/_layout.tsx` | Add Capsule tab |
| 4.6 | `app/lib/api.ts` | Add `outfitApi.buildCapsule()` |
| 4.7 | `server/app/services/fashion_rating_service.py` | New — rating logic |
| 4.7 | `server/app/routers/fashion_rating.py` | New — rating endpoints |
| 4.7 | `server/app/main.py` | Register rating router |
| 4.7 | `app/app/(tabs)/style-rating.tsx` | New screen |
| 4.7 | `app/app/(tabs)/_layout.tsx` | Add Style Rating tab |
| 4.7 | `app/lib/api.ts` | Add `fashionRatingApi` |
| 4.8 | `server/app/services/calendar_service.py` | New — wear tracking |
| 4.8 | `server/app/routers/calendar.py` | Add analytics endpoints |
| 4.8 | `app/app/(tabs)/calendar.tsx` | Add wear-frequency UI |

---

### Dependencies & Config

| Dependency | Required For | Setup |
|------------|-------------|-------|
| Gemini API key (existing) | 4.2, 4.3, 4.5, 4.7 | Already in `.env` |
| OpenWeatherMap API key | 4.4 | Add `WEATHER_API_KEY` to `.env` |
| Expo Location | 4.4 | `npx expo install expo-location` |
| None new | 4.1, 4.6, 4.8 | Uses existing infrastructure |

---

### Implementation Order

```
Phase 4.1 — Closet Gap Analysis (quickest win, validates endpoint pattern)
       ↓
Phase 4.2 — AI Stylist (validates Gemini explain pattern)
       ↓
Phase 4.3 — Smart Outfit Generator (builds on 4.2)
       ↓
Phase 4.4 — Weather Recommendations (needs API key first)
       ↓
Phase 4.5 — AI Packing Assistant (standalone feature)
       ↓
Phase 4.6 — Capsule Wardrobe Builder (algorithm-heavy)
       ↓
Phase 4.7 — AI Fashion Rating (Gemini Vision)
       ↓
Phase 4.8 — Calendar Enhancements (polish pass)
```

Each phase should be fully tested before moving to the next.

# StyleMate — Step-by-Step AI Build Prompts

## How to use this

- Give these to an AI coding agent **one step at a time**, not all at once. Wait for each step to finish, run/test the app, then move to the next.
- Best tool for this: an agentic coding tool that can create files and run commands directly in a project folder (e.g. Claude Code). A plain chat window works too, but you'll have to copy code manually.
- Each step is self-contained. Copy the text inside the code block and paste it as your prompt.
- Steps are grouped into phases. Finish a phase before starting the next — later prompts assume earlier ones exist.
- Keep a single project folder for the whole build so the AI can see previous files when you paste the next prompt.

---

## PHASE 0 — Project Setup

### Step 0.1 — Initialize the project

```
Create a new project called "StyleMate" with two folders:
- /app : a React Native app using Expo (TypeScript)
- /server : a Python FastAPI backend

Set up /app with Expo Router and basic navigation with 4 empty screens:
Home, Wardrobe, Add Item, Outfit Suggestions.

Set up /server with FastAPI, a health check endpoint at /health,
SQLite database using SQLAlchemy, and a requirements.txt.

Create a README.md explaining how to run both the app and the server locally.
```

### Step 0.2 — Create a project context file

```
Create a file called PROJECT_CONTEXT.md at the root of the project.
In it, summarize: what StyleMate is (an AI wardrobe and outfit-pairing app),
the tech stack (React Native/Expo frontend, FastAPI/SQLite backend),
and the planned features (wardrobe scanning, AI tagging, outfit pairing,
calendar, body type filter, shopping suggestions, virtual try-on, hairstyle try-on).
Keep this file updated as a running summary every time we add a major feature,
so future prompts have context.
```

---

## PHASE 1 — MVP: Wardrobe + AI Tagging + Pairing

### Step 1.1 — Database models

```
In /server, create SQLAlchemy models for:
- User (id, name, email, gender, style_preference)
- ClothingItem (id, user_id, image_url, category, color, pattern,
  occasion_tag, season, created_at)

Add a database migration/init script and a seed script with 5 sample
clothing items for testing.
```

### Step 1.2 — Image upload endpoint

```
In /server, add a POST /upload-image endpoint that accepts an image file,
saves it to a local /uploads folder (create a helper so this can be swapped
for cloud storage like S3 or Cloudinary later), and returns the image URL.
Add basic validation for file type and size.
```

### Step 1.3 — AI tagging endpoint

```
In /server, add a POST /tag-item endpoint that:
1. Accepts an image URL
2. Sends it to an AI vision model with a prompt asking it to return
   JSON with: category (top/bottom/dress/outerwear/footwear/accessory),
   dominant_color, pattern (solid/striped/printed/checked/other),
   occasion_tag (casual/office/ethnic/party/formal/loungewear), and season.
3. Parses and returns that JSON.

Use an environment variable for the AI API key. Add clear error handling
if the AI response isn't valid JSON (retry once, then return a fallback
"unclassified" tag set rather than crashing).
```

### Step 1.4 — Connect "Add Item" screen

```
In /app, build the "Add Item" screen:
1. Let the user take a photo or pick one from the gallery
2. Upload it to POST /upload-image
3. Send the returned URL to POST /tag-item
4. Show the AI's suggested tags in editable fields (category, color,
   pattern, occasion, season) so the user can correct them
5. On confirm, save the item via a new POST /clothing-items endpoint
   in the backend, then navigate back to the Wardrobe screen

Add a loading state while the AI is tagging, and an error state if it fails.
```

### Step 1.5 — Wardrobe screen

```
In /app, build the Wardrobe screen as a grid of clothing items pulled from
GET /clothing-items (create this endpoint in /server if it doesn't exist).
Each item shows its photo and category. Add filter chips at the top for
category and occasion_tag. Tapping an item opens a detail view with all
its tags and a delete button (wire up DELETE /clothing-items/{id}).
```

### Step 1.6 — Rule-based pairing engine

```
In /server, create a new module pairing_engine.py with a function
suggest_outfits(user_id, occasion_tag=None) that:
1. Loads the user's clothing items
2. Groups them by category (top, bottom, footwear, accessory)
3. Scores combinations using simple rules:
   - neutral colors (black/white/beige/grey/navy) pair with anything
   - same color family (monochrome) is a safe high score
   - complementary colors (basic color wheel opposites) score well
   - clashing bright patterns together score low
   - if occasion_tag is given, only use items matching that tag
4. Returns the top 5 scored outfit combinations as JSON,
   each with a short plain-English reason for the pairing

Add a GET /outfit-suggestions endpoint that calls this function.
Write 3-4 unit tests for the scoring logic using sample items.
```

### Step 1.7 — Outfit Suggestions screen

```
In /app, build the Outfit Suggestions screen that calls
GET /outfit-suggestions and displays each suggested outfit as a card
showing the paired items' photos side by side, plus the reason text
underneath. Add a refresh button to re-generate suggestions.
```

**Checkpoint:** At this point you have a working MVP — scan clothes, get tagged, get outfit suggestions. Test it fully before moving on.

---

## PHASE 2 — Calendar, Body Type, Feedback Loop

### Step 2.1 — Calendar/occasion planning

```
In /server, add a CalendarEntry model (id, user_id, date, occasion_tag,
locked_outfit_id nullable) and endpoints: POST /calendar-entries,
GET /calendar-entries, PATCH /calendar-entries/{id}.

In /app, build a Calendar screen where the user taps a date, picks an
occasion_tag from a dropdown, and gets outfit suggestions filtered to
that occasion (reuse /outfit-suggestions with the occasion_tag param).
Let the user "lock in" a suggested outfit for that date.
```

### Step 2.2 — Body type input

```
In /server, add a body_type field to the User model with options
(rectangle, hourglass, pear, apple, inverted_triangle). Add a
POST /users/{id}/body-type endpoint to set it manually via a simple
questionnaire for now (skip photo-based detection — we'll add that later
if needed). In /app, add a short onboarding questionnaire screen for this.
```

### Step 2.3 — Bias suggestions using body type

```
In /server, update pairing_engine.py so suggest_outfits also takes the
user's body_type and gives a small score boost to items/silhouettes
that are commonly recommended for that body type (e.g. wrap styles and
belted waists score higher for "rectangle" and "apple" body types).
Keep this as a simple additive scoring rule, not a separate model.
```

### Step 2.4 — Like/dislike feedback loop

```
In /server, add an OutfitFeedback model (id, user_id, outfit_item_ids,
liked boolean, created_at) and a POST /outfit-feedback endpoint.
Update suggest_outfits to slightly boost scores for color/category
combinations the user has liked before, and lower scores for ones
they've disliked, based on their feedback history.

In /app, add thumbs up/down buttons to each outfit suggestion card
that call this endpoint.
```

---

## PHASE 3 — Shopping Suggestions

### Step 3.1 — Flipkart affiliate integration

```
In /server, create a new module shopping_service.py with a function
search_flipkart(query: str) that calls the Flipkart Affiliate API
(use environment variables FLIPKART_AFFILIATE_ID and
FLIPKART_AFFILIATE_TOKEN) and returns product name, image, price,
and affiliate link for the top 5 results. Add error handling for
rate limits and API failures with a graceful empty-result fallback.
```

### Step 3.2 — "Complete the look" gap detection

```
In /server, add a function in pairing_engine.py called find_gaps(user_id)
that looks at the user's wardrobe and detects missing categories or weak
combinations (e.g. lots of tops but no matching neutral bottoms).
For each gap, generate a short shopping search query describing the
ideal item (e.g. "beige wide leg trousers women") using an AI text call.
Add a GET /shopping-suggestions endpoint that runs find_gaps and then
calls search_flipkart for each gap, returning combined results.
```

### Step 3.3 — Shopping UI

```
In /app, add a "Complete the Look" section to the Outfit Suggestions
screen that calls GET /shopping-suggestions and shows product cards
(image, price, name) that open the affiliate link in the browser when tapped.
```

> Note: check the current Amazon affiliate API docs before integrating — Amazon has been migrating affiliates from the old Product Advertising API to a newer "Creators API," so confirm which one is live when you get to this step. Meesho does not currently offer a public product-search affiliate API, so skip direct integration there for now; a simple "search on Meesho" deep link is a reasonable placeholder.

---

## PHASE 4 — Virtual Try-On

### Step 4.1 — Photo capture + consent

```
In /app, build a "My Photo" screen where the user uploads a full-body
photo for try-on purposes. Before allowing upload, show a clear consent
screen explaining the photo will be used only for virtual try-on
rendering and can be deleted anytime. Add a "delete my photo" button
that calls a new DELETE /users/{id}/photo endpoint in /server.
```

### Step 4.2 — Try-on API integration

```
In /server, create try_on_service.py with a function generate_tryon(
user_photo_url, garment_image_url) that calls a virtual try-on API
(use an environment variable TRYON_API_KEY; structure the function so
the provider — e.g. FASHN.ai or Kling — can be swapped via a config
value). Add a POST /try-on endpoint. Add per-user rate limiting
(max 5 generations per day) stored in a new TryOnUsage table.
```

### Step 4.3 — Try-on UI

```
In /app, add a "Try It On" button on each outfit suggestion card that
calls POST /try-on and shows a loading spinner, then displays the
rendered image full-screen with save/share buttons. Show a friendly
message if the user hits their daily rate limit.
```

### Step 4.4 — Hairstyle try-on (optional add-on)

```
In /server, extend try_on_service.py with generate_hairstyle_tryon(
user_photo_url, hairstyle_reference) using the same pattern as the
clothing try-on function. In /app, add a simple hairstyle picker
(grid of preset style thumbnails) on the try-on result screen that
lets the user preview a hairstyle change on the same rendered photo.
```

---

## PHASE 5 — Polish & Publish

### Step 5.1 — Privacy & settings

```
In /app, build a Settings screen with: privacy policy link, "delete my
account and all data" button (wire this to a new DELETE /users/{id}
endpoint in /server that cascades and deletes all related records and
uploaded photos), and a toggle for notifications.
Draft a plain-language privacy policy page explaining what photos are
stored, why, and how to delete them.
```

### Step 5.2 — Polish pass

```
Review the whole /app codebase and add: loading skeletons for all
data-fetching screens, empty states (e.g. "Your wardrobe is empty,
add your first item" with a CTA button), and consistent error toasts
for failed API calls. Do not change any business logic, only UX polish.
```

### Step 5.3 — Build configuration

```
Set up EAS Build configuration in /app for both Android and iOS,
including app icon and splash screen placeholders, app name "StyleMate",
and a proper bundle identifier. Create a BUILD.md explaining the exact
commands to build and submit to both the Play Store and App Store.
```

### Step 5.4 — Store listing content

```
Write Play Store and App Store listing content for StyleMate: a short
description (under 80 characters), a full description (under 4000
characters), and 5 suggested screenshot captions describing what each
screenshot should show.
```

---

## Tips for running this well

- Test after every single step before moving to the next — small steps are easy to debug, big batches aren't.
- If a step fails or produces something broken, just describe the error back to the AI in your next message rather than re-pasting the whole step.
- Keep API keys out of your prompts — tell the AI to use environment variables, and set the actual values yourself in a `.env` file.
- Phases 3 and 4 depend on external accounts (Flipkart Affiliate Program, a try-on API provider) — sign up for those before you reach that step so you have real keys ready.
