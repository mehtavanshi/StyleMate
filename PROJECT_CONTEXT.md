# PROJECT_CONTEXT.md

## What is StyleMate?

StyleMate is an **AI-powered wardrobe management and outfit-pairing app**. It helps users catalog their clothing, get AI-driven outfit suggestions, plan outfits for events/calendar, and explore shopping recommendations — all personalized to their style, body type, and lifestyle.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React Native + Expo (TypeScript), Expo Router for navigation |
| **Backend** | Python FastAPI, SQLAlchemy ORM, SQLite database |
| **Database** | SQLite (local, file-based) |

## Planned Features

### Phase 1 — MVP: Wardrobe + AI Tagging + Pairing (current)

#### Step 1.1 — Database Models ✅
- [x] User model (id, name, email, gender, style_preference, created_at)
- [x] ClothingItem model (id, user_id FK, image_url, category, color, pattern, occasion_tag, season, brand, name, formality, tags, created_at, updated_at)
- [x] User-ClothingItem one-to-many relationship
- [x] Pydantic schemas: UserCreate, UserResponse, ClothingItemCreate, ClothingItemUpdate, ClothingItemResponse
- [x] API routes: /users/ (GET, POST), /users/{id} (GET), /clothing/ (GET, POST), /clothing/{id} (GET, PUT, DELETE)
- [x] Database init script: `scripts/init_db.py` — creates all tables
- [x] Seed script: `scripts/seed_db.py` — creates demo user + 5 sample items
- [x] Sample items: White Oxford Shirt, Blue Denim Jeans, Black Leather Jacket, Navy Blue Chinos, White Running Sneakers

### Phase 2 — AI Tagging & Scanning
- [ ] Wardrobe scanning — photograph clothing items to auto-detect category, color, pattern
- [ ] AI tagging — auto-label items by style, formality, season, occasion

### Phase 3 — Outfit Pairing
- [ ] AI outfit suggestions based on wardrobe contents, weather, and occasion
- [ ] Outfit scoring (style compatibility, color harmony)
- [ ] Save and rate favorite outfits

### Phase 4 — Calendar & Planning
- [ ] Outfit calendar — plan what to wear for upcoming days/events
- [ ] Event-based suggestions (work, date night, gym, wedding, etc.)

### Phase 5 — Personalization
- [ ] Body type filter — suggestions that complement user's body shape
- [ ] Style profile — learn user preferences over time

### Phase 6 — Shopping & Discovery
- [ ] Shopping suggestions — recommend pieces to fill wardrobe gaps
- [ ] Link to stores for recommended items

### Phase 7 — Advanced Visualization
- [ ] Virtual try-on — see how an outfit looks on your body type
- [ ] Hairstyle try-on — match hairstyles to outfits and face shape

---

**Last updated:** Step 1.1 — New database models (User, ClothingItem), migration script, seed script with 5 sample items.
