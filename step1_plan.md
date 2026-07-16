# StyleMate — Phase 1 Fix: Better Pairing + Gender Filter (Open Source Only)

## What's changing and why

- **Gender filter:** add a `target_gender` field so wardrobe items and suggestions can be filtered to men's/women's/unisex.
- **Better color logic:** replace naive rules with real HSL-based color-harmony math (built into Python, free).
- **Better style matching:** use **FashionCLIP** — a free, open-source AI model made specifically for fashion — to score how well items actually go together stylistically, instead of guessing with hand-written rules.
- **Optional advanced upgrade:** use **outfit-transformer**, an open-source model pretrained on the real Polyvore outfit dataset, for a genuinely learned compatibility score.

All of this runs locally, no paid API required for these specific pieces.

Feed these prompts one at a time, same as before.

---

### Step 1 — Add gender/target filter

```
In /server, add a target_gender field (values: men, women, unisex) to both
the User model and the ClothingItem model. Add a migration for existing
data (default existing items to "unisex" if unset). Update
POST /clothing-items to accept target_gender, and update
GET /clothing-items and GET /outfit-suggestions to accept an optional
target_gender query param that filters results.

In /app, add a gender toggle (Men/Women/Unisex) on the Add Item screen
and as a filter chip on the Wardrobe and Outfit Suggestions screens.
```

### Step 2 — Replace naive color rules with real color-harmony math

```
In /server, rewrite the color-scoring part of pairing_engine.py to use
proper HSL color theory instead of a hardcoded neutral/complementary list:
1. Convert each item's dominant_color (hex or RGB, already stored) to HSL
   using Python's built-in colorsys module.
2. Score color pairs based on actual hue-angle relationships:
   - hue difference under ~15 degrees = analogous (high score)
   - hue difference around 150-210 degrees = complementary (high score)
   - hue difference around 90-150 or 210-270 = clashing (low score,
     unless one item has very low saturation, i.e. it's a neutral)
   - very low saturation (grey/black/white/beige) items always score
     as safely compatible with anything
3. Replace the old hardcoded color list logic entirely with this function.
   Write 5 unit tests with known color pairs and expected score ranges
   (e.g. navy + white should score high, orange + red-violet should
   score low unless one is neutral).
```

### Step 3 — Set up FashionCLIP locally

```
In /server, add a new module style_embeddings.py that:
1. Loads the open-source "patrickjohncyh/fashion-clip" model from
   Hugging Face (via the transformers and torch libraries — add these
   to requirements.txt)
2. Has a function get_embedding(image_path_or_url) that returns the
   image's embedding vector as a list of floats
3. Has a function cosine_similarity(vec_a, vec_b) for comparing two
   embeddings

Add a background job (or a simple function called after item creation)
that computes and stores the FashionCLIP embedding for every clothing
item in a new column (store as JSON or a separate EmbeddingCache table).
Make sure this runs on CPU if no GPU is available — note the expected
slower speed in a comment, and add a simple in-memory cache so we don't
recompute embeddings for items that already have one.
```

### Step 4 — Blend embedding similarity into the pairing score

```
In /server, update pairing_engine.py so the final compatibility score
for a pair of items is a weighted blend:
- 50% color-harmony score (from Step 2)
- 35% FashionCLIP style-embedding cosine similarity (from Step 3)
- 15% hard-rule bonus/penalty (occasion match, formality match,
  target_gender match — items must match target_gender or be unisex,
  this is a hard filter not a soft score)

Make the weights configurable constants at the top of the file so they're
easy to tune later. Re-run the unit tests from Step 2 and add 3 new tests
that check the blended score behaves sensibly on a few sample item pairs.
```

### Step 5 — Use FashionCLIP for free tagging too (optional, replaces paid API)

```
In /server, extend style_embeddings.py with a function
zero_shot_classify(image_path_or_url, candidate_labels: list[str]) that
uses FashionCLIP's zero-shot classification (compare the image embedding
against text embeddings of the candidate labels, return the best match
and its confidence score).

Update the /tag-item endpoint to optionally use this function instead of
the paid AI vision API — pass in candidate label lists for category
(top, bottom, dress, outerwear, footwear, accessory), pattern (solid,
striped, printed, checked), and target_gender (men, women, unisex).
Keep the old paid-API path available behind a config flag called
TAGGING_PROVIDER (values: "fashion_clip" or "vision_api") so it's easy
to switch back and compare quality.
```

### Step 6 — Sanity-check script

```
In /server, create a script scripts/eval_pairing.py that takes a small
hardcoded list of "known good" outfit pairs and "known bad" outfit pairs
(write 8-10 of each based on common sense — e.g. white shirt + navy
trousers = good, orange top + red-pink bottoms = bad) and runs them
through suggest_outfits' scoring function, printing whether the new
scoring correctly ranks the good pairs above the bad ones. Use this to
tune the weights from Step 4 if results look off.
```

### Step 7 (optional, bigger upgrade) — Real learned compatibility model

```
In /server, add an optional advanced scoring module using the open-source
outfit-transformer project (github.com/owj0421/outfit-transformer),
which is pretrained on the Polyvore outfit-compatibility dataset:
1. Set it up as a separate local service or script that loads the
   pretrained checkpoint
2. Add a function get_learned_compatibility(item_image_urls: list[str])
   that returns a compatibility score for a set of items
3. In pairing_engine.py, add a config flag USE_LEARNED_COMPATIBILITY
   that, when true, blends this score in alongside the Step 4 blend
   (e.g. 40% learned score, 30% color, 20% FashionCLIP similarity,
   10% hard rules) instead of the Step 4 weights
4. Document in PROJECT_CONTEXT.md that this step requires more setup
   (downloading checkpoint weights) and more compute per request, so
   it's optional and can be toggled off if it's too slow.
```

---

## Notes

- Steps 1-6 alone should meaningfully improve pairing quality and are lightweight enough to run without a GPU.
- Step 7 is the "do this if you want research-grade pairing quality" step — skip it for now and come back once Steps 1-6 are solid.
- Everything here (colorsys, FashionCLIP, outfit-transformer) is free and open source — no new paid API keys needed for this part of the app.
