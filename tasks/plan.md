# Implementation Plan: Garment-Detection Gate for Add-Item Tagging Pipeline

## Overview

Add a pre-check step to the FashionCLIP tagging pipeline that rejects non-clothing images before attribute classification begins. Currently, FashionCLIP forces every image into the closest-scoring clothing labels (e.g. a blank black photo gets tagged as "bottom, trousers, solid, formal"). This plan adds a garment-detection gate, raises confidence thresholds, fixes confidence-default bugs, surfaces errors on the frontend, and adds tests.

## Architecture Decisions

- **Garment detection lives in `style_embeddings.py`** — it uses the same FashionCLIP model and embedding infrastructure as the rest of the pipeline, keeping all CLIP logic in one place.
- **The gate is called at the top of `_tag_item_fashion_clip()`** before any attribute tagging, so non-clothing images fail fast without wasting compute on category/color/pattern classification.
- **422 HTTP status for rejection** — semantically correct (unprocessable entity: the image does not contain a detectable garment). The frontend already handles non-2xx responses as errors.
- **Threshold alignment**: `STYLE_TAG_THRESHOLD` and `EMBELLISHMENT_THRESHOLD` both raised to `CONFIDENCE_THRESHOLD` (0.24) so the same bar applies across all field types.

## Task List

### Task 1: Add `detect_garment()` to `style_embeddings.py`

**Description:** Add a new function `detect_garment(image_url: str) -> tuple[bool, float]` that uses FashionCLIP zero-shot classification with three candidate labels:
- "a photo of a single clothing item on a plain background"
- "a blank, blurry, or non-clothing photo"
- "a photo of a person, object, or scene that is not primarily clothing"

Returns `(is_garment, confidence)` where `is_garment` is True only if the clothing label is the top match AND the margin over the second-best label is >= 0.10.

**Acceptance criteria:**
- Function uses existing `get_embedding()` and `get_ensembled_label_embedding()` infrastructure
- Returns `(False, score)` when the top match is a non-clothing label
- Returns `(False, score)` when the margin between top and second-best is < 0.10 (near-random)
- Returns `(True, score)` when clothing label wins with sufficient margin

**Files touched:**
- `server/app/style_embeddings.py` — add `detect_garment()` function after `zero_shot_classify_multi()`

**Estimated scope:** Small (1 file, ~30 lines)

---

### Task 2: Add garment-detection gate to `_tag_item_fashion_clip()` in `tagging.py`

**Description:** Call `detect_garment()` at the top of `_tag_item_fashion_clip()` before any attribute tagging. On rejection, raise `HTTPException(status_code=422, detail={"error": "no_garment_detected", "message": "..."})`.

**Acceptance criteria:**
- Gate is called before the `CANDIDATE_LABELS` loop (line 343)
- On rejection, returns 422 with structured JSON error body
- On success, pipeline proceeds normally

**Files touched:**
- `server/app/routers/tagging.py` — add gate call at start of `_tag_item_fashion_clip()`

**Estimated scope:** Small (1 file, ~15 lines)

---

### Task 3: Raise confidence thresholds for style_tags and embellishments

**Description:** Raise `STYLE_TAG_THRESHOLD` from 0.12 to 0.24 and `EMBELLISHMENT_THRESHOLD` from 0.15 to 0.24 so they align with `CONFIDENCE_THRESHOLD` (0.24).

**Acceptance criteria:**
- `STYLE_TAG_THRESHOLD` = 0.24 in `style_embeddings.py`
- `EMBELLISHMENT_THRESHOLD` = 0.24 in `fashion_taxonomy.py`
- Low-confidence predictions on passing images get flagged for review (via `needs_review`)

**Files touched:**
- `server/app/style_embeddings.py` — line 237
- `server/app/fashion_taxonomy.py` — line 79

**Estimated scope:** XS (2 files, 2 lines each)

---

### Task 4: Fix confidence default bugs in `tagging.py`

**Description:** Fix three places where missing confidence defaults to 1.0 (high value) instead of 0.0 (low value):

1. **Line 290 (Gemini path):** `raw_conf.get(field, 1.0)` → `raw_conf.get(field, 0.0)`
2. **Line 483 (color sanity check):** `confidence.get("dominant_color", 1.0)` → `confidence.get("dominant_color", 0.0)`
3. **Lines 435, 530 (unconditional confidence=1.0 for embellishments/style_tags):** These are set to 1.0 when the operation succeeds, but they should reflect actual model confidence, not a hardcoded maximum. Compute real confidence from the scores returned by `zero_shot_binary_check` and `zero_shot_classify_multi`.

**Acceptance criteria:**
- Missing confidence defaults to 0.0 everywhere
- Embellishments and style_tags confidence reflects actual model scores
- `needs_review` is set to `True` when confidence is below `CONFIDENCE_THRESHOLD` for these fields

**Files touched:**
- `server/app/routers/tagging.py` — lines 290, 435, 483, 530

**Estimated scope:** Medium (1 file, ~20 lines)

---

### Task 5: Update `TagResult` interface and frontend error handling

**Description:** Add an optional `_error` field to `TagResult` in `api.ts` so the frontend can distinguish garment-detection rejections from other errors. Update `add-item.tsx` to show a specific retry prompt for `no_garment_detected` errors instead of a generic failure.

**Acceptance criteria:**
- `TagResult` interface includes `_error?: string` field
- Frontend shows a specific "No garment detected" message with a retry button when the backend returns 422 with `no_garment_detected`
- Other errors still show the generic error message

**Files touched:**
- `app/lib/api.ts` — add `_error` to `TagResult`
- `app/(tabs)/add-item.tsx` — update error handling in `handleTagImage` and error step UI

**Estimated scope:** Small (2 files, ~20 lines)

---

### Task 6: Add test fixtures and write test suite

**Description:** Create test fixtures for non-clothing images and write tests covering:
1. Blank black image → rejected with `no_garment_detected`
2. Solid-color image → rejected
3. Photo of a wall → rejected
4. Photo of a face → rejected
5. Normal clothing photo (floral-dress.jpg) → passes through and tags correctly

**Acceptance criteria:**
- All 4 non-clothing fixtures are rejected with the correct error
- The clothing fixture still passes and produces valid tags
- Tests run with `pytest server/tests/test_tagging_gate.py`

**Files touched:**
- `server/tests/fixtures/` — add 4 new fixture images (black.png, solid_color.png, wall.jpg, face.jpg)
- `server/tests/test_tagging_gate.py` — new test file

**Estimated scope:** Medium (1 new file + 4 fixture images)

---

### Task 7: Verify end-to-end and run tests

**Description:** Run all existing tests plus the new tagging gate tests. Verify no regressions.

**Acceptance criteria:**
- All existing tests pass
- New garment-detection gate tests pass
- No lint/typecheck errors

**Files touched:** None (verification only)

**Estimated scope:** Small

---

## Checkpoints

### Checkpoint: After Tasks 1-2
- [ ] `detect_garment()` function exists and returns correct (is_garment, confidence) tuples
- [ ] `_tag_item_fashion_clip()` calls the gate before attribute tagging
- [ ] Non-clothing images get 422 with structured error

### Checkpoint: After Tasks 3-4
- [ ] Thresholds raised to 0.24
- [ ] Confidence defaults fixed (no more 1.0 defaults)
- [ ] Embellishments/style_tags confidence reflects real scores

### Checkpoint: After Tasks 5-6
- [ ] Frontend shows specific retry prompt for no_garment_detected
- [ ] Test fixtures created and tests written
- [ ] All tests pass

### Checkpoint: After Task 7
- [ ] Full test suite passes
- [ ] No regressions

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| FashionCLIP garment detection may misclassify unusual clothing (e.g. accessories only) as non-garment | Medium | Set margin threshold low (0.10) to reduce false negatives; accessories-only items can still be tagged manually |
| Test fixtures for non-clothing images need to be real images | Low | Create simple generated images programmatically (solid black, solid color, gradient) using PIL |
| Raising thresholds may reduce tag coverage for some garments | Medium | This is intentional — low-confidence tags should be flagged for review, not saved as fact |

## Open Questions

- Should the garment detection use the same text templates as the existing `LABEL_TEMPLATES` in `style_embeddings.py`, or custom ones? → Using custom ones as specified in the requirements.
- Should the 422 error response body include a `detail` key (FastAPI default) or a custom structure? → Use FastAPI's standard `HTTPException` with `detail` as a dict containing `error` and `message` keys.
