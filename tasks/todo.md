# Task List: Garment-Detection Gate for Add-Item Tagging Pipeline

## Task 1: Add `detect_garment()` to `style_embeddings.py`
**Status:** pending
**Priority:** high
**Acceptance criteria:**
- Function uses existing `get_embedding()` and `get_ensembled_label_embedding()` infrastructure
- Returns `(False, score)` when the top match is a non-clothing label
- Returns `(False, score)` when the margin between top and second-best is < 0.10
- Returns `(True, score)` when clothing label wins with sufficient margin

## Task 2: Add garment-detection gate to `_tag_item_fashion_clip()` in `tagging.py`
**Status:** pending
**Priority:** high
**Acceptance criteria:**
- Gate is called before the `CANDIDATE_LABELS` loop
- On rejection, returns 422 with structured JSON error body
- On success, pipeline proceeds normally

## Task 3: Raise confidence thresholds for style_tags and embellishments
**Status:** pending
**Priority:** high
**Acceptance criteria:**
- `STYLE_TAG_THRESHOLD` = 0.24 in `style_embeddings.py`
- `EMBELLISHMENT_THRESHOLD` = 0.24 in `fashion_taxonomy.py`

## Task 4: Fix confidence default bugs in `tagging.py`
**Status:** pending
**Priority:** high
**Acceptance criteria:**
- Missing confidence defaults to 0.0 everywhere (Gemini path, color sanity check)
- Embellishments and style_tags confidence reflects actual model scores
- `needs_review` is set to `True` when confidence is below `CONFIDENCE_THRESHOLD`

## Task 5: Update `TagResult` interface and frontend error handling
**Status:** pending
**Priority:** high
**Acceptance criteria:**
- `TagResult` interface includes `_error?: string` field
- Frontend shows a specific "No garment detected" message with a retry button
- Other errors still show the generic error message

## Task 6: Add test fixtures and write test suite
**Status:** pending
**Priority:** high
**Acceptance criteria:**
- All 4 non-clothing fixtures are rejected with the correct error
- The clothing fixture still passes and produces valid tags
- Tests run with `pytest server/tests/test_tagging_gate.py`

## Task 7: Verify end-to-end and run tests
**Status:** pending
**Priority:** medium
**Acceptance criteria:**
- All existing tests pass
- New garment-detection gate tests pass
- No lint/typecheck errors
