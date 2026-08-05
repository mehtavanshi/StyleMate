# Backend Bug Audit (Unique Findings Only)

## Critical

| #   | Check | File                             | Line(s) | Description                                                                                                       | Impact                                                | Severity     |
| --- | ----- | -------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- | ------------ |
| C1  | [x]   | `server/app/routers/wardrobe.py` | 1-64    | Imports nonexistent `WardrobeItem` model and undefined schemas. Router is dead code and not mounted in `main.py`. | Would immediately fail with `ImportError` if enabled. | **Critical** |

---

## High

| #   | Check | File                                     | Line(s)  | Description                                                                                               | Impact                                                                         | Severity |
| --- | ----- | ---------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | -------- |
| H1  | [x]   | `server/app/routers/calendar.py`         | 151-168  | `link_try_on_image()` auto-creates a `CalendarEntry` with hardcoded `user_id=1` when entry doesn't exist. | Calendar data can be attributed to the wrong user.                             | **High** |
| H2  | [x]   | `server/app/services/weather_service.py` | 49       | `rule_for_temp()` fallback returns an integer instead of a rule dictionary.                               | Weather filtering can crash on invalid/extreme temperatures.                   | **High** |
| H3  | [x]   | `server/app/pairing_engine.py`           | 860, 870 | Outfit explanation emits `"balanced silhouette"` twice from different scoring components.                 | Duplicate explanation fragments reduce explanation quality.                    | **High** |
| H4  | [ ]   | `server/app/recommender.py`              | 246-260  | Recommendation score silently defaults to `0.5` when model or user data is unavailable.                   | Makes recommender appear functional while actually disabled.                   | **High** |
| H5  | [ ]   | `server/app/style_embeddings.py`         | 377-408  | Background embedding computation commits independently after request completes.                           | Newly uploaded clothing may temporarily receive neutral recommendation scores. | **High** |
| H6  | [ ]   | `server/app/pairing_engine.py`           | 512-545  | `_silhouette_balance_score()` ignores Indian ethnic wear categories despite existing silhouette rules.    | Ethnic outfits lose silhouette scoring quality.                                | **High** |

---

## Medium

| #   | Check | File                                             | Line(s)           | Description                                                                               | Impact                                                           | Severity   |
| --- | ----- | ------------------------------------------------ | ----------------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ---------- |
| M1  | [ ]   | `server/app/pairing_engine.py`                   | 362               | `_pick_color_for_gap()` always falls back to `"beige"` when colors can't be determined.   | Recommendations become repetitive.                               | **Medium** |
| M2  | [ ]   | `server/app/pairing_engine.py`                   | 988-1009          | Valid body types with empty rule sets silently receive zero boost.                        | Certain body types never receive style optimization.             | **Medium** |
| M3  | [x]   | `server/app/style_match.py`                      | 848               | Uses `"olive green"` while color map only supports `"olive"`.                             | Color scoring and shopping queries fail for that recommendation. | **Medium** |
| M4  | [x]   | `server/app/pairing_engine.py`                   | 191-195           | Fuzzy color matching depends on dictionary insertion order.                               | Ambiguous colors can resolve inconsistently.                     | **Medium** |
| M5  | [ ]   | `server/app/routers/outfits.py`                  | 196-209           | Outfit feedback endpoint accepts arbitrary `user_id` values without ownership validation. | Training data can be polluted with fake feedback.                | **Medium** |
| M6  | [ ]   | `server/app/models.py`                           | 45,51             | Stores both `formality` and `formality_score` independently.                              | Values can drift and contradict each other.                      | **Medium** |
| M7  | [ ]   | `server/app/routers/clothing.py`                 | 84,94             | Delete/update routes redundantly invalidate cached item state after database cleanup.     | Unnecessary work with no functional benefit.                     | **Medium** |
| M8  | [x]   | `server/app/routers/tagging.py`                  | 482-496           | Color sanity check defaults confidence to `1.0` when confidence value is missing.         | Real confidence-writing failures become hidden.                  | **Medium** |
| M9  | [ ]   | `server/app/pairing_engine.py` + `pair_cache.py` | 1098-1118 / 61-72 | Capsule builder queries wardrobe twice.                                                   | Extra database work.                                             | **Medium** |
| M10 | [ ]   | `server/app/services/packing_service.py`         | 110-119           | Packing endpoint blocks synchronously while waiting for Gemini.                           | Worker thread can remain blocked for up to one minute.           | **Medium** |
| M11 | [ ]   | `server/app/routers/shopping.py`                 | 86-89             | Any provider exception becomes HTTP 502 instead of degrading gracefully.                  | Temporary provider failures break the whole endpoint.            | **Medium** |

---

## Low

| #   | Check | File                                            | Line(s) | Description                                                              | Impact                                                           | Severity |
| --- | ----- | ----------------------------------------------- | ------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------- | -------- |
| L1  | [ ]   | `server/app/pairing_engine.py`                  | 636-638 | Missing embeddings silently return neutral similarity.                   | Difficult to diagnose missing embeddings.                        | **Low**  |
| L2  | [ ]   | `server/app/pairing_engine.py`                  | 452-460 | Missing fabric information silently receives neutral score.              | Missing metadata isn't visible.                                  | **Low**  |
| L3  | [ ]   | `server/app/pairing_engine.py`                  | 463-467 | Unknown fit combinations default to neutral score.                       | Unsupported fit combinations are hidden.                         | **Low**  |
| L4  | [ ]   | `server/app/main.py`                            | 36-37   | Database tables auto-create only for SQLite.                             | PostgreSQL deployments require manual schema setup.              | **Low**  |
| L5  | [ ]   | `server/app/pairing_engine.py`                  | 921     | Empty outfit returns 0.0 while single-item outfit returns 0.5.           | Inconsistent scoring baseline.                                   | **Low**  |
| L6  | [ ]   | `server/app/pairing_engine.py`                  | 186-188 | `_color_to_hsl()` doesn't normalize repeated whitespace.                 | Minor normalization inconsistency.                               | **Low**  |
| L7  | [ ]   | `server/app/routers/tagging.py`                 | 567-569 | Unknown `TAGGING_PROVIDER` values silently fall back to Gemini.          | Environment typo can unexpectedly consume paid API credits.      | **Low**  |
| L8  | [ ]   | `server/app/style_advisor.py`                   | 211     | Lazy loading triggers an additional SQL query during outfit explanation. | Minor N+1 performance issue.                                     | **Low**  |
| L9  | [ ]   | `server/app/services/fashion_rating_service.py` | 78      | Rating cache key uses only photo URL.                                    | Different users sharing the same URL may receive cached results. | **Low**  |
| L10 | [ ]   | `server/app/routers/upload.py`                  | 31-33   | Retrying tagging uploads the same image again.                           | Duplicate storage consumption.                                   | **Low**  |

---

# Frontend Bug Audit

## Medium

| #   | Check | File                             | Line(s) | Description                                                                               | Impact                                                              | Severity   |
| --- | ----- | -------------------------------- | ------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ---------- |
| M12 | [x]   | `app/app/(tabs)/index.tsx`       | 227-233 | Settings icon calls `router.push("/app/settings")` but correct route is `/settings`.      | Tapping Settings shows "no route found" error; navigation broken.   | **Medium** |
| M15 | [x]   | `app/app/style-match.tsx` + `server/app/routers/style_match.py` | 73, 115-129 / 17-22 | Initial fetch uses default `limit=6` per category; load-more uses higher limit, returning better/diverse results. | Users see subpar static suggestions first — only getting good results after tapping "Load More". | **Medium** |
| M16 | [ ]   | `app/components/ImageEditor.tsx` | 152-188 | JPEG intermediate saves cause generational quality loss on every crop/rotate; only 90° rotation; crop error silently dismisses with no feedback. | Each crop/rotate degrades image quality; no fine rotation control; silent failures confuse users. | **Medium** |
| M13 | [x]   | `app/app/capture.tsx`            | 126-128 | `.resize({ width: MAX_LONG_EDGE_PX })` always constrains width, not the actual long edge. | Portrait images get oversized (long edge unchecked); defeats resize purpose. | **Medium** |
| M14 | [x]   | `app/app/(tabs)/wardrobe.tsx`    | 69, 71, 103-109 | Category & gender filter chips use `Set<string>` allowing multi-selection instead of single-select. | Users can accidentally select multiple categories/genders, contrary to expected filter behavior. | **Medium** |
| M17 | [x]   | `app/app/style-match.tsx`        | 178-191 | All category sections render regardless of selected item type or wardrobe count — e.g. "Matching Tops" shown even when item is a top. | Cluttered UI with irrelevant sections; users see empty categories. | **Medium** |
| M18 | [x]   | `app/capsule.tsx`                | 37      | Capsule default is 20 (`useState(20)`) but user wants 10.                                                                         | Users get larger than desired capsule by default.                   | **Medium** |
| M19 | [ ]   | `app/app/(tabs)/index.tsx`       | 407-422 | Upcoming section shows only date number as plain text instead of a merged outfit image (top+bottom+footwear+accessories).          | Users can't see what outfit is upcoming — just a date.              | **Medium** |
| M20 | [x]   | `app/app/(tabs)/wardrobe.tsx`    | —       | Gap between wardrobe title and search bar; color inconsistencies throughout the screen.                                           | Visual polish issues in wardrobe UI.                                | **Medium** |
| M21 | [ ]   | `app/app/(tabs)/add-item.tsx` + server | — | Adding items is slow — upload → AI tagging → save roundtrip is slow. Embedding computation happens async after creation. | Poor UX; users wait too long after adding an item.                  | **Medium** |
| M22 | [ ]   | `app/app/(tabs)/calendar.tsx`    | —       | Calendar shows only dots/dates with no outfit images on dates. User wants outfit images displayed on calendar dates.              | Calendar is not visually informative; user can't see outfits at a glance. | **Medium** |

## Low

| #   | Check | File                             | Line(s) | Description                                                                               | Impact                                                              | Severity |
| --- | ----- | -------------------------------- | ------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | -------- |
| L11 | [ ]   | `app/app/(tabs)/index.tsx`       | 144-153 | Avatar press shows Alert instead of navigating to a proper screen; no back button.        | Users can't navigate to a profile/settings page with back support.  | **Low**  |
| L12 | [x]   | `app/app/(tabs)/wardrobe.tsx`    | 209-210 | Odd item count leaves last row item without `columnWrapperStyle` spacing (`marginBottom`). | Last item in odd-count grid appears visually disconnected from the row above it. | **Low**  |
| L13 | [ ]   | `app/app/(tabs)/calendar.tsx`    | 411-487 | Outfit suggestions in bottom sheet use horizontal FlatList that doesn't work properly; should be vertical scroll with 2 items per row. | Users can't browse outfit suggestions — horizontal scroll broken/unintuitive. | **Low**  |
| L14 | [x]   | `app/app/(tabs)/outfit-suggestions.tsx` | — | UI gap issues; like/dislike button UX needs improvement. | Visual polish and interaction quality issues. | **Low**  |

---

# Summary

| Severity     |                          Count |
| ------------ | -----------------------------: |
| **Critical** |                              1 |
| **High**     |                              6 |
| **Medium**   |                             22 |
| **Low**      |                             14 |
| **Total**    | **43 Unique Findings (28 Backend + 15 Frontend)** |

---

# Additional logic bugs found in the 2026-07-31 audit pass (fixed)

| #   | Check | File                                    | Description                                                                                                                              | Severity |
| --- | ----- | --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| N1  | [x]   | `app/app/(tabs)/index.tsx`              | Home read `.length` off the `{outfits, total}` envelope, so "Today's Outfit" never rendered.                                              | **High** |
| N2  | [x]   | `app/app/(tabs)/outfit-suggestions.tsx` | Feedback / try-on / explanation state keyed by list index — after refresh or a filter change, position N holds a different outfit and inherits the previous one's like, try-on result and explanation. | **High** |
| N3  | [x]   | `app/components/ImageEditor.tsx`        | `imgW/imgH` already hold post-rotation dimensions; a second rotation-parity swap flipped the axes twice, so crop-after-rotate cut the wrong region. | **High** |
| N4  | [x]   | `server/app/style_embeddings.py`        | Tagging one item ran the CLIP image encoder ~20× on the same photo (once per field / subcategory stage / embellishment check). Now cached per URL. | **Medium** (perf) |
| N5  | [x]   | `app/app/(tabs)/my-tryons.tsx`          | Same stretched-last-card bug as the wardrobe grid, on both try-on grids.                                                                   | **Low**  |
