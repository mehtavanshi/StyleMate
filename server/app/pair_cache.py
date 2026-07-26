"""Persistent cache of pairwise compatibility scores.

Scoring one pair is fast; the problem is there are O(n^2) of them and every
capsule / outfit request rescored the whole wardrobe from scratch. This module
computes each pair once, stores it, and afterwards only scores pairs it has
never seen — so adding one item costs n new scores, not n^2.

Usage:

    scores = ensure_pair_scores(db, user_id)   # {frozenset({a_id, b_id}): score}

Call invalidate_item() whenever an item's scoring inputs change, and
invalidate_user() when the user's body_type changes (score_pair reads it).
"""

from __future__ import annotations

import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import ClothingItem, ItemPairScore, User
from app.pairing_engine import _capsule_pairable, score_pair

logger = logging.getLogger(__name__)

# Rows written per flush. Keeps a first-run backfill on a large wardrobe from
# building one enormous INSERT.
_CHUNK = 500


def _key(a_id: int, b_id: int) -> tuple[int, int]:
    """Canonical (low, high) ordering so a pair has one representation."""
    return (a_id, b_id) if a_id < b_id else (b_id, a_id)


def invalidate_item(db: Session, item_id: int) -> int:
    """Drop every cached pair involving this item. Returns rows removed.

    Caller commits. Deliberately not relying on the FK cascade: an *update*
    (recoloured, recategorised) invalidates too, and that fires no cascade.
    """
    removed = (
        db.query(ItemPairScore)
        .filter(or_(ItemPairScore.item_a_id == item_id, ItemPairScore.item_b_id == item_id))
        .delete(synchronize_session=False)
    )
    return removed


def invalidate_user(db: Session, user_id: int) -> int:
    """Drop the user's whole cache — for changes that reprice every pair."""
    return (
        db.query(ItemPairScore)
        .filter(ItemPairScore.user_id == user_id)
        .delete(synchronize_session=False)
    )


def ensure_pair_scores(
    db: Session,
    user_id: int,
    items: list[ClothingItem] | None = None,
) -> dict[frozenset[int], float]:
    """Return every pairable score for the user, computing only what's missing.

    Pass ``items`` to score a pre-filtered subset; the cache is still keyed by
    item id, so a filtered call reuses whatever a full call already stored.
    """
    if items is None:
        items = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
    if len(items) < 2:
        return {}

    ids = {i.id for i in items}
    cached: dict[frozenset[int], float] = {}
    for row in (
        db.query(ItemPairScore)
        .filter(
            ItemPairScore.user_id == user_id,
            ItemPairScore.item_a_id.in_(ids),
            ItemPairScore.item_b_id.in_(ids),
        )
        .all()
    ):
        cached[frozenset((row.item_a_id, row.item_b_id))] = row.score

    user = db.query(User).filter(User.id == user_id).first()
    body_type = getattr(user, "body_type", None) if user else None

    fresh: list[dict] = []
    for idx, a in enumerate(items):
        for b in items[idx + 1:]:
            if not _capsule_pairable(a.category, b.category):
                continue
            k = frozenset((a.id, b.id))
            if k in cached:
                continue
            score, _, _ = score_pair(a, b, body_type)
            cached[k] = score
            lo, hi = _key(a.id, b.id)
            fresh.append(
                {"user_id": user_id, "item_a_id": lo, "item_b_id": hi, "score": score}
            )

    if fresh:
        logger.info(
            "pair_cache: computed %d new pairs for user %s (%d served from cache)",
            len(fresh), user_id, len(cached) - len(fresh),
        )
        for start in range(0, len(fresh), _CHUNK):
            db.bulk_insert_mappings(ItemPairScore, fresh[start:start + _CHUNK])
        db.commit()

    return cached
