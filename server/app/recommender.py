"""Feedback-driven outfit recommender.

Builds a user × combo interaction matrix from ``OutfitFeedback`` rows and
trains a LightFM model (with an ``implicit`` ALS fallback) to score candidate
outfit combos for a user. Combo identity is a deterministic hash of the sorted
item IDs so it matches the dedup key used in ``pairing_engine.suggest_outfits``.
"""

import hashlib
import json
import os
import pickle
from typing import Optional

from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models import ClothingItem, OutfitFeedback

DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
    "recommender.pkl",
)


def _combo_id(item_ids: list[int]) -> str:
    """Deterministic combo id for a set of item ids (order-independent)."""
    sorted_ids = sorted(int(i) for i in item_ids)
    payload = json.dumps(sorted_ids, separators=(",", ":"))
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def _parse_style_tags(raw) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(t).strip().lower() for t in parsed if t]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _parse_outfit_item_ids(raw: str) -> list[int]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [int(i) for i in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _item_features(item: ClothingItem) -> list[str]:
    feats: list[str] = []
    if item.category:
        feats.append(f"cat:{item.category.lower()}")
    if item.color:
        feats.append(f"color:{item.color.lower()}")
    if item.pattern:
        feats.append(f"pattern:{item.pattern.lower()}")
    if item.occasion_tag:
        feats.append(f"occasion:{item.occasion_tag.lower()}")
    if item.season:
        feats.append(f"season:{item.season.lower()}")
    if item.formality:
        feats.append(f"formality:{item.formality.lower()}")
    for tag in _parse_style_tags(getattr(item, "style_tags", None)):
        feats.append(f"tag:{tag}")
    return feats


def build_interaction_matrix(db: Session):
    from scipy.sparse import coo_matrix

    rows = db.query(OutfitFeedback).all()
    if not rows:
        return coo_matrix((0, 0)), {}, {}

    user_map: dict[int, int] = {}
    combo_map: dict[str, int] = {}
    data: list[float] = []
    row_idx: list[int] = []
    col_idx: list[int] = []

    for fb in rows:
        user_id = fb.user_id
        if user_id not in user_map:
            user_map[user_id] = len(user_map)
        item_ids = _parse_outfit_item_ids(fb.outfit_item_ids)
        cid = _combo_id(item_ids)
        if cid not in combo_map:
            combo_map[cid] = len(combo_map)
        data.append(1.0 if fb.liked else -1.0)
        row_idx.append(user_map[user_id])
        col_idx.append(combo_map[cid])

    matrix = coo_matrix(
        (data, (row_idx, col_idx)),
        shape=(len(user_map), len(combo_map)),
    )
    return matrix, user_map, combo_map


def _has_lightfm() -> bool:
    try:
        import lightfm  # noqa: F401

        return True
    except Exception:
        return False


def build_item_features(db: Session, combo_ids: list[str]):
    """Build LightFM item features: union of features across each combo's items.

    Returns ``(None, feature_map)`` when LightFM is unavailable so the implicit
    fallback can still train using latent factors alone.
    """
    rows = db.query(OutfitFeedback).all()
    combo_to_items: dict[str, list[int]] = {}
    all_item_ids: set[int] = set()
    for fb in rows:
        item_ids = _parse_outfit_item_ids(fb.outfit_item_ids)
        cid = _combo_id(item_ids)
        combo_to_items.setdefault(cid, [])
        for iid in item_ids:
            combo_to_items[cid].append(iid)
            all_item_ids.add(iid)

    items_by_id: dict[int, ClothingItem] = {}
    if all_item_ids:
        fetched = db.query(ClothingItem).filter(ClothingItem.id.in_(all_item_ids)).all()
        items_by_id = {it.id: it for it in fetched}

    feature_map: dict[str, list[str]] = {}
    for cid, item_ids in combo_to_items.items():
        feats: list[str] = []
        for iid in item_ids:
            item = items_by_id.get(iid)
            if item:
                feats.extend(_item_features(item))
        # dedupe while preserving order
        seen = set()
        unique_feats = []
        for f in feats:
            if f not in seen:
                seen.add(f)
                unique_feats.append(f)
        feature_map[cid] = unique_feats

    if not _has_lightfm():
        return None, feature_map

    from lightfm.data import Dataset

    dataset = Dataset()
    dataset.fit_partial(items=combo_ids)
    item_features = dataset.build_item_features(feature_map)
    return item_features, feature_map


def _try_import_lightfm():
    return _has_lightfm()


def train_model(db: Session, model_path: str = DEFAULT_MODEL_PATH) -> dict:
    import numpy as np

    interactions, user_map, combo_map = build_interaction_matrix(db)
    combo_ids = list(combo_map.keys())

    item_features = None
    feature_map: dict[str, list[str]] = {}
    if combo_ids:
        item_features, feature_map = build_item_features(db, combo_ids)

    use_lightfm = _try_import_lightfm()
    model = None

    if use_lightfm and combo_ids:
        from lightfm import LightFM

        model = LightFM(loss="warp", no_components=30, random_state=42)
        model.fit(
            interactions,
            item_features=item_features,
            epochs=20,
            num_threads=4,
        )
    elif combo_ids:
        import implicit

        csr = interactions.tocsr()
        pos = csr.multiply((csr > 0).astype(np.float64)).tocsr()
        als = implicit.als.AlternatingLeastSquares(use_gpu=False, factors=30)
        als.fit(pos.T)
        model = als
    else:
        model = None

    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    payload = {
        "model": model,
        "backend": "lightfm" if use_lightfm else "implicit",
        "user_map": user_map,
        "combo_map": combo_map,
        "combo_to_items": {cid: combo_to_items_lookup(db)[cid] for cid in combo_ids},
        "feature_map": feature_map,
        "item_features": item_features,
    }
    with open(model_path, "wb") as f:
        pickle.dump(payload, f)

    n_features = item_features.shape[1] if item_features is not None else 0
    return {
        "model_path": model_path,
        "backend": payload["backend"],
        "n_users": len(user_map),
        "n_combos": len(combo_map),
        "n_features": int(n_features),
    }


def combo_to_items_lookup(db: Session) -> dict[str, list[int]]:
    rows = db.query(OutfitFeedback).all()
    out: dict[str, list[int]] = {}
    for fb in rows:
        item_ids = _parse_outfit_item_ids(fb.outfit_item_ids)
        cid = _combo_id(item_ids)
        if cid not in out:
            out[cid] = item_ids
    return out


def get_recommendation_score(
    user_id: int,
    item_ids: list[int],
    model_path: str = DEFAULT_MODEL_PATH,
) -> float:
    import numpy as np

    if not os.path.exists(model_path):
        return 0.5

    with open(model_path, "rb") as f:
        payload = pickle.load(f)

    user_map = payload.get("user_map", {})
    combo_map = payload.get("combo_map", {})
    combo_to_items = payload.get("combo_to_items", {})
    feature_map = payload.get("feature_map", {})
    model = payload.get("model")

    cid = _combo_id(item_ids)

    if user_id not in user_map or cid not in combo_map or model is None:
        return 0.5

    user_idx = user_map[user_id]
    combo_idx = combo_map[cid]
    backend = payload.get("backend", "lightfm")

    if backend == "lightfm":
        item_features = payload.get("item_features")
        scores = model.predict(
            user_idx, [combo_idx], item_features=item_features
        )
        raw = float(np.asarray(scores).ravel()[0])
        score = 1.0 / (1.0 + np.exp(-raw))
        return float(min(1.0, max(0.0, score)))

    # implicit fallback: dot product of user/item factors
    try:
        user_factors = model.user_factors
        item_factors = model.item_factors
        u = np.asarray(user_factors[user_idx]).ravel()
        v = np.asarray(item_factors[combo_idx]).ravel()
        raw = float(np.dot(u, v))
    except Exception:
        return 0.5

    score = 1.0 / (1.0 + np.exp(-raw))
    return float(min(1.0, max(0.0, score)))
