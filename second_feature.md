# WEAK / UNDERBAKED FEATURE AUDIT — StyleMate

## Methodology

Each finding is rated on three axes (1–10 scale):

- **Impact (I):** How much this affects user trust/experience
- **Confidence (C):** How certain this is a real problem
- **Ease (E):** How easy it is to fix (higher = easier)

ICE Score = **Impact × Confidence × Ease**

---

# AUDIT TABLE (Duplicates Removed, Virtual Try-On Removed)

| Rank | ICE      | Feature     | Finding                                                       | File:Line                                  | What's Wrong                                                   | Real Consequence                                                                   |
| ---- | -------- | ----------- | ------------------------------------------------------------- | ------------------------------------------ | -------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| 1    | **1000** | Shopping    | Meesho & Amazon providers fabricate fake products             | `shopping_service.py:175-234`              | Returns fake placeholder products instead of real API results. | Users see blank images, ₹0 prices, and generic search redirects, destroying trust. |
| 2    | **1000** | Tagging     | `style_tags` computed but never saved                         | `tagging.py`, `add-item.tsx`, `api.ts`     | AI generates style tags that frontend ignores entirely.        | Style-aware outfit recommendations never work.                                     |
| 3    | **1000** | Tagging     | Missing **kurti** category in frontend                        | `add-item.tsx` vs `tagging.py`             | Backend supports it but frontend doesn't.                      | Indian ethnic wear becomes incorrectly categorized and unfilterable.               |
| 4    | **900**  | Calendar    | Calendar stores only one clothing item instead of full outfit | `models.py`, `calendar.tsx`, `schemas.py`  | Only first clothing item is stored.                            | Outfit history and wear analytics become inaccurate.                               |
| 5    | **900**  | Shopping    | Flipkart affiliate tracking missing                           | `shopping_service.py`                      | Product URLs aren't affiliate links.                           | No commission earned from purchases.                                               |
| 6    | **900**  | Shopping    | Only first shopping provider is queried                       | `routers/shopping.py`                      | Multi-provider architecture exists but unused.                 | Backup providers never contribute results.                                         |
| 7    | **810**  | Outfit      | Smart Outfit ignores extracted formality, season and vibe     | `routers/outfits.py`, `nlp_router.py`      | NLP extracts data but recommendation engine ignores it.        | Results don't match the user's requested style.                                    |
| 8    | **810**  | Outfit      | LightFM recommendation engine is effectively dead             | `pairing_engine.py`, `recommender.py`      | User feedback never influences future recommendations.         | Like/Dislike buttons provide no personalization.                                   |
| 9    | **800**  | Shopping    | FashionCLIP visual ranking introduces huge latency            | `style_embeddings.py`, `shop_matches.py`   | Every product image is downloaded and embedded.                | Shop suggestions can take 30–100 seconds.                                          |
| 10   | **800**  | Shopping    | Myntra & Ajio search URLs are malformed                       | `style_match.py`                           | Query parameters missing.                                      | Links frequently open 404 pages.                                                   |
| 11   | **720**  | Tagging     | Black denim automatically changed to navy                     | `tagging.py`                               | Hardcoded override increases confidence.                       | Incorrect color stored with no review warning.                                     |
| 12   | **720**  | Tagging     | Empty metadata can be saved                                   | `add-item.tsx`                             | Required AI review fields aren't validated before save.        | Wardrobe contains incomplete items that hurt recommendations.                      |
| 13   | **720**  | Outfit      | Explain Outfit endpoint lacks ownership checks                | `routers/style_advice.py`                  | Accepts arbitrary item IDs.                                    | Possible wardrobe information leak.                                                |
| 14   | **720**  | Calendar    | Duplicate calendar entries allowed                            | `models.py`, `calendar.py`                 | Missing unique constraint on `(user_id, date)`.                | Wear analytics become inflated.                                                    |
| 15   | **720**  | Calendar    | Deleting wardrobe items leaves broken calendar references     | `clothing.py`, `models.py`                 | No cleanup of calendar records.                                | Dangling references and data loss.                                                 |
| 16   | **640**  | Outfit      | Weather endpoint exposes developer configuration message      | `routers/outfits.py`                       | Internal setup instructions shown to users.                    | Poor UX and information leakage.                                                   |
| 17   | **640**  | Outfit      | Dresses never paired with jackets/blazers                     | `pairing_engine.py`                        | Outfit generator omits outerwear for dresses.                  | Common outfit combinations never appear.                                           |
| 18   | **640**  | Outfit      | Gender filtering excludes unisex clothing                     | `pairing_engine.py`                        | Exact gender matching removes unisex items.                    | Smaller recommendation pool.                                                       |
| 19   | **630**  | Style Match | `/style-advice` endpoint exists but UI never calls it         | `routers/style_advice.py`, `api.ts`        | Fully implemented backend feature is orphaned.                 | Users never access the most advanced shopping assistant.                           |
| 20   | **630**  | Wardrobe    | Complete Outfit endpoint never used                           | `wardrobe/[id].tsx`, `clothing.py`         | Frontend calls simpler endpoint instead.                       | Missed opportunity to generate complete outfits.                                   |
| 21   | **600**  | Tagging     | Formality review indicator never shown                        | `add-item.tsx`, `tagging.py`               | Review flag always disabled.                                   | Incorrect formality scores remain unnoticed.                                       |
| 22   | **600**  | Tagging     | Formality score can be stored as null                         | `add-item.tsx`                             | Null values accepted.                                          | Outfit filtering becomes inconsistent.                                             |
| 23   | **600**  | Shopping    | Complete the Look uses generic search URLs                    | `matching_service.py`, `shopping_links.py` | Search links instead of actual products.                       | Poor shopping experience and no affiliate revenue.                                 |
| 24   | **600**  | Shopping    | Duplicate Meesho links generated                              | `style_match.py`                           | Same store appears twice.                                      | Confusing UI.                                                                      |
| 25   | **560**  | Outfit      | Fallback "Why this works?" explanation is unhelpful           | `style_advisor.py`                         | Internal compatibility labels shown to users.                  | AI explanation appears broken.                                                     |
| 26   | **540**  | Tagging     | Review status isn't persisted                                 | `tagging.py`, `add-item.tsx`               | AI uncertainty disappears after save.                          | Users can't revisit uncertain classifications.                                     |
| 27   | **540**  | Tagging     | Saree/Lehenga categorized as Kurti                            | `fashion_taxonomy.py`                      | Incorrect garment hierarchy.                                   | Outfit generation becomes inaccurate.                                              |
| 28   | **540**  | Shopping    | Gap analysis only counts categories                           | `pairing_engine.py`                        | Doesn't recognize similar colors/styles.                       | Suggests purchases user effectively already owns.                                  |
| 29   | **500**  | Outfit      | "Date" interpreted as "Party"                                 | `nlp_router.py`                            | Keyword mapping is inaccurate.                                 | Wrong outfit recommendations.                                                      |
| 30   | **500**  | Outfit      | Outfit diversity resets between pages                         | `pairing_engine.py`                        | Load More ignores previous diversity state.                    | Repetitive outfit suggestions.                                                     |
| 31   | **490**  | Tagging     | Gender classifier margin too small                            | `style_embeddings.py`                      | Tiny similarity differences determine gender.                  | Unisex clothing often misclassified.                                               |
| 32   | **490**  | Outfit      | Neutral wardrobes generate repetitive outfits                 | `pairing_engine.py`                        | Neutral colors receive identical scores.                       | Low outfit variety.                                                                |
| 33   | **490**  | Outfit      | Small wardrobes fail silently                                 | `pairing_engine.py`                        | No onboarding guidance.                                        | New users receive empty recommendations.                                           |
| 34   | **480**  | Shopping    | Missing affiliate disclosure                                  | Shopping modules                           | No disclosure for affiliate links.                             | Regulatory compliance risk.                                                        |
| 35   | **450**  | Style Match | Shopping recommendations use static templates                 | `style_match.py`                           | Personalized scores applied to fake products.                  | Personalization appears misleading.                                                |
| 36   | **450**  | Style Match | Unknown colors fall back to static recommendations            | `style_match.py`                           | Color theory engine bypassed.                                  | Generic shopping suggestions.                                                      |
| 37   | **450**  | Capsule     | Outfit count measures pairs, not complete outfits             | `pairing_engine.py`                        | Misleading statistics.                                         | Users overestimate item usefulness.                                                |
| 38   | **450**  | Wardrobe    | Dead wardrobe router references nonexistent models            | `wardrobe.py`                              | Unused legacy code.                                            | Maintenance confusion.                                                             |
| 39   | **420**  | Tagging     | Duplicate FORMALITY_MAP definitions                           | Frontend & Backend                         | Two copies may diverge.                                        | Maintenance risk.                                                                  |
| 40   | **420**  | Tagging     | Gemini lacks dedicated gender classifier                      | `tagging.py`                               | Relies entirely on free-form LLM output.                       | Less reliable gender classification.                                               |
| 41   | **420**  | Tagging     | Confidence threshold too low                                  | `style_embeddings.py`                      | Near-random predictions accepted.                              | Incorrect classifications stored confidently.                                      |
| 42   | **420**  | Tagging     | Pattern list mismatch                                         | Frontend vs Backend                        | Frontend includes "other"; backend doesn't.                    | Non-standard values stored.                                                        |
| 43   | **420**  | Shopping    | Shopping endpoints handle failures inconsistently             | Shopping routers                           | Different APIs return different error behavior.                | Inconsistent user experience.                                                      |
| 44   | **420**  | Shopping    | Shop link queries are too generic                             | `matching_service.py`                      | Missing gender, occasion and subtype.                          | Low-quality shopping results.                                                      |
| 45   | **420**  | Style Match | Duplicate wardrobe lists in API response                      | `style_match.py`                           | Same data serialized twice.                                    | Wasted bandwidth.                                                                  |
| 46   | **400**  | Tagging     | Dupatta missing from Gemini taxonomy                          | `fashion_taxonomy.py`, `tagging.py`        | Gemini never predicts it correctly.                            | Manual correction always required.                                                 |
| 47   | **400**  | Tagging     | Unknown occasions default to formality 3                      | `tagging.py`                               | Invalid fallback value.                                        | Formal clothing misclassified.                                                     |
| 48   | **400**  | Tagging     | No visible Review Required banner                             | `add-item.tsx`                             | Review state easy to miss.                                     | Users unknowingly save incomplete data.                                            |
| 49   | **360**  | Tagging     | No retry for FashionCLIP failures                             | `style_embeddings.py`                      | Partial failures leave missing metadata.                       | Less reliable tagging.                                                             |
| 50   | **360**  | Tagging     | Color validation only checks white                            | `tagging.py`                               | Other color mistakes ignored.                                  | Incorrect colors persist.                                                          |
| 51   | **360**  | Tagging     | No content-type validation when downloading images            | `tagging.py`                               | HTML pages can be processed as images.                         | Invalid AI tagging results.                                                        |
| 52   | **360**  | Outfit      | Weather recommendations silently degrade                      | `routers/outfits.py`                       | Falls back without informing users.                            | Reduced trust in recommendations.                                                  |
| 53   | **360**  | Outfit      | Fragile SQL LIKE occasion filtering                           | `pairing_engine.py`                        | Uses substring matching.                                       | Potential future filtering bugs.                                                   |
| 54   | **360**  | Outfit      | Duplicate feedback records possible                           | Frontend                                   | No deduplication.                                              | Recommendation dataset becomes noisy.                                              |
| 55   | **360**  | Shopping    | Meesho URL builders inconsistent                              | Shopping modules                           | Two different builders produce different URLs.                 | Confusing behavior.                                                                |
| 56   | **360**  | Shopping    | API cannot distinguish fake vs real products                  | Shopping API                               | Missing discriminator field.                                   | Frontend cannot render appropriately.                                              |
| 57   | **360**  | Shopping    | Shop match fit metadata copied from source item               | Shopping                                   | Fit belongs to selected item, not recommended product.         | Misleading compatibility.                                                          |
| 58   | **360**  | Shopping    | Provider configuration silently ignores typos                 | `shopping_service.py`                      | Unknown providers skipped.                                     | Admins believe providers are active when they aren't.                              |
| 59   | **360**  | Style Match | Owned and generated items mixed together                      | `style_match.py`                           | Difficult to distinguish owned vs suggested.                   | Confusing shopping experience.                                                     |
| 60   | **360**  | Style Match | Fashion Rating unavailable without Gemini                     | `fashion_rating_service.py`                | No heuristic fallback.                                         | Feature unusable offline/free mode.                                                |
| 61   | **360**  | Style Match | Packing ignores real weather service                          | `packing_service.py`                       | Hallucinates weather instead of using API.                     | Packing recommendations may be wrong.                                              |
| 62   | **360**  | Calendar    | Same outfit can be scheduled repeatedly                       | `calendar.py`                              | No duplicate outfit validation.                                | Poor planning experience.                                                          |
| 63   | **320**  | Tagging     | Accessories taxonomy too broad                                | `fashion_taxonomy.py`                      | Many culturally distinct accessories grouped together.         | Reduced classification accuracy.                                                   |
| 64   | **320**  | Outfit      | Cached outfit generation is never used                        | `pairing_engine.py`                        | Dead caching system.                                           | Wasted storage and maintenance.                                                    |
| 65   | **300**  | Style Match | Packing list capped regardless of trip duration               | `packing_service.py`                       | 14-day and 60-day trips look similar.                          | Long-trip recommendations become unrealistic.                                      |
| 66   | **300**  | Style Match | Packing shopping links ignore gender                          | `packing_service.py`                       | Generic search queries.                                        | Less relevant products.                                                            |
| 67   | **300**  | Style Match | Fashion rating ignores wardrobe context                       | `fashion_rating_service.py`                | Rates only uploaded image.                                     | Doesn't reflect personal style.                                                    |
| 68   | **300**  | Style Match | Packing destination unsanitized                               | `routers/packing.py`                       | Prompt injection possibility.                                  | Security and reliability risk.                                                     |
| 69   | **240**  | Style Match | Non-neutral suggestions bypass the 70% quality threshold      | `style_match.py:64,270`                    | `STYLE_VARIETY_THRESHOLD=62` lets colorful items through at 62% instead of the standard 70% | Users see low-match suggestions (62-69%) that don't meet the quality bar. |
| 70   | **224**  | Style Match | Initial page size shows 5 items instead of compact 2-3        | `style-match.tsx:46`                       | `PAGE_SIZE=5` dumps too many items on first load.             | Overwhelming initial display; "Load More" pattern underutilized. |
| 71   | **216**  | Style Match | Empty category sections still render instead of hiding        | `style-match.tsx:287-292`                  | `MatchSection` always renders a `<Section>` with placeholder text even when items list is empty | Cluttered UI with multiple pointless empty-state messages. |
| 72   | **175**  | Wardrobe    | Filter chips are bulky, lack visual hierarchy & multi-select clarity | `wardrobe.tsx:132-158`                 | Large flat chip rows for category/occasion/gender take too much space; no grouping, icons, or active-state contrast. | Filter bar feels oversized and cluttered; harder to browse wardrobe. |
| 73   | **150**  | Wardrobe    | Gappy layout and color inconsistency between header, search bar, and filter chips | `wardrobe.tsx:174-186` | Tab header → search bar spacing is loose; `filterBar` uses `colors.surface` while search input uses `"#f0f0f0"`. | Looks disjointed — feels like separate components rather than a cohesive UI. |
| 74   | **200**  | Outfit      | Like/dislike buttons use faded transparent colors (look disabled) and feedback never influences recommendations | `outfit-suggestions.tsx:595-620`, `pairing_engine.py` | Buttons styled with `colors.success + "55"` / `colors.danger + "33"` (very low alpha); LightFM engine is dead — feedback saved but never used. | Users think feedback is broken or ignored; no incentive to engage with it. |

---

# TOP 5 SYSTEMIC RISKS

1. **Fake Shopping Infrastructure**
   - Shopping providers fabricate products instead of retrieving real listings.
   - Downstream shopping features inherit misleading data.

2. **Dead Recommendation Pipeline**
   - LightFM personalization, cached outfits, and `/style-advice` are built but never actually used.

3. **Calendar Design Limitation**
   - Calendar stores only a single clothing item instead of a complete outfit, degrading outfit history and analytics.

4. **Tagging Pipeline Loses Valuable AI Output**
   - `style_tags` are generated but discarded before persistence, preventing style-aware recommendations.

5. **Disconnected Features**
   - Several advanced backend capabilities (Style Advice, Complete Outfit, Cached Outfits) are implemented but never connected to the user interface.

---

# SUMMARY BY FEATURE

| Feature            | Findings |
| ------------------ | -------: |
| Tagging            |       18 |
| Shopping           |       16 |
| Outfit Suggestions |       16 |
| Style Match        |       14 |
| Calendar           |        5 |
| Wardrobe           |        4 |
| Capsule Wardrobe   |        1 |
