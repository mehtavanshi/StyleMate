# Plan: LightFM Recommender Training Pipeline

## Goal
Add a feedback-driven recommender that learns from `OutfitFeedback` (liked/disliked outfit combos) and can score candidate combos for a user.

## Dependencies
Add to `server/requirements.txt`:
- `lightfm` (primary)
- `implicit` (fallback if LightFM fails to install)
- `scipy` (already transitively available via numpy, but explicit is safer)
- `scikit-learn` (for feature hashing / one-hot if needed)

## New Files
| File | Purpose |
|---|---|
| `server/app/recommender.py` | Core recommender module |
| `server/scripts/retrain_recommender.py` | Manual/scheduled retrain script |
| `server/models/recommender.pkl` | Saved model artifact (gitignored) |

## Modified Files
| File | Change |
|---|---|
| `server/.gitignore` | Add `models/` and `*.pkl` |

---

## `server/app/recommender.py` Design

### Data structures
- **Combo ID**: `hashlib.sha1(json.dumps(sorted_item_ids, separators=(',', ':')).encode()).hexdigest()[:12]`
  - Deterministic for the same set of item IDs regardless of order.
- **Interaction matrix**: `scipy.sparse.coo_matrix` of shape `(n_users, n_combos)`.
  - `liked=1`, `disliked=-1`.
- **Item features**: Built via `lightfm.data.Dataset`. Each combo is a LightFM "item" whose features are the **union** of features from all items in the combo.

### Functions

#### `build_interaction_matrix(db: Session) -> (sparse_matrix, user_map, combo_map)`
1. Query all `OutfitFeedback` rows.
2. For each row:
   - `user_idx` = user_map[user_id]
   - `combo_id` = hash of sorted `outfit_item_ids`
   - `combo_idx` = combo_map[combo_id]
   - value = `1` if liked else `-1`
3. Build `coo_matrix((data, (row, col)), shape=(n_users, n_combos))`.
4. Return matrix + mappings (needed for prediction lookup).

#### `build_item_features(db: Session, combo_ids: list[str]) -> (sparse_matrix, feature_map)`
1. For each `combo_id`:
   - Look up the `ClothingItem` rows by `outfit_item_ids` (requires joining to the original feedback or passing the mapping).
   - Collect features: `category`, `color`, `pattern`, and parsed `style_tags`.
   - Union them into a single feature list per combo.
2. Use `lightfm.data.Dataset.build_item_features` to create a sparse matrix.
3. Return matrix + feature mapping.

**Note**: To avoid N+1 queries, fetch all needed `ClothingItem` rows in a single query keyed by ID.

#### `train_model(db: Session, model_path: str = "server/models/recommender.pkl") -> dict`
1. Call `build_interaction_matrix` and `build_item_features`.
2. If LightFM is available:
   - `lightfm.LightFM(loss='warp', no_components=30, random_state=42)`
   - `model.fit(interactions, item_features=item_features, epochs=20, num_threads=4)`
3. Else fallback to `implicit`:
   - Build CSR matrix (only positive interactions `liked=1`).
   - `implicit.als.AlternatingLeastSquares(use_gpu=False, factors=30)`
   - `model.fit(ratings.T)`  # implicit expects items x users
   - Wrap in a simple callable that returns a float score.
4. Serialize model + mappings + feature metadata with `pickle`.
5. Return `{"n_users": ..., "n_combos": ..., "n_features": ...}`.

#### `get_recommendation_score(user_id: int, item_ids: list[int], model_path: str = "server/models/recommender.pkl") -> float`
1. Load pickle.
2. `combo_id = hash of sorted item_ids`.
3. If `combo_id` not in `combo_map`, return `0.5` (neutral / unseen).
4. Get `user_idx` and `combo_idx`.
5. Predict:
   - LightFM: `model.predict(user_idx, combo_idx, item_features=item_features)`
   - Implicit fallback: compute dot product of user/item factors, normalize to [0, 1].
6. Return float score clamped to [0, 1].

---

## `server/scripts/retrain_recommender.py`

Standalone script mirroring the pattern in `seed_db.py`:
1. `sys.path.insert` to allow `app.*` imports.
2. `Base.metadata.create_all(bind=engine)` (idempotent).
3. Open `SessionLocal()`.
4. Call `train_model(db)`.
5. Log training stats (n_users, n_combos, n_features).
6. Exit cleanly.

Usage:
```bash
cd server && python scripts/retrain_recommender.py
```

---

## Scheduling
- **Manual**: Run the script via cron or systemd timer.
- **Optional future**: Add a lightweight APScheduler background task in `app/main.py` that runs nightly. Not required for initial implementation.

---

## Validation
1. `pip install lightfm` — verify Cython extension compiles.
2. Run `python scripts/seed_db.py` to ensure sample data exists.
3. Add a few `OutfitFeedback` rows manually or via the existing API.
4. Run `python scripts/retrain_recommender.py` and verify:
   - `server/models/recommender.pkl` is created.
   - No exceptions.
5. In a Python REPL:
   ```python
   from app.recommender import get_recommendation_score
   score = get_recommendation_score(1, [1, 2, 3])
   print(score)
   ```
   Should return a float in [0, 1].

---

## Risks & Mitigations
| Risk | Mitigation |
|---|---|
| LightFM fails to compile (missing Cython/build tools) | Document `implicit` fallback in requirements; add a check in `train_model`. |
| Cold-start (new user or new combo with no feedback) | Return `0.5` neutral score for unseen combos/users. |
| Feature sparsity | Union of features is simple; if combos have no matching training features, LightFM still works via latent factors. |
| Model file in git | Add `models/` and `*.pkl` to `.gitignore`. |

---

## Open Questions (resolved)
- **Combo identity**: Hash of sorted item IDs. ✅
- **Model path**: `server/models/`. ✅
- **Combo features**: Union of all item features. ✅
