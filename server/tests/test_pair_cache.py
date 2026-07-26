"""Pair-score cache: results must match uncached scoring, and go stale correctly."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ClothingItem, ItemPairScore, User
from app.pair_cache import ensure_pair_scores, invalidate_item, invalidate_user
from app.pairing_engine import _capsule_pairable, score_pair


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, name="T", email="t@example.com"))
    for i, (cat, color) in enumerate(
        [("top", "black"), ("top", "white"), ("bottom", "blue"),
         ("bottom", "beige"), ("footwear", "white")], start=1
    ):
        session.add(ClothingItem(id=i, user_id=1, name=f"item{i}", category=cat, color=color))
    session.commit()
    yield session
    session.close()


def _items(db):
    return db.query(ClothingItem).filter(ClothingItem.user_id == 1).all()


def test_cached_scores_match_direct_scoring(db):
    cached = ensure_pair_scores(db, 1)
    items = _items(db)
    checked = 0
    for idx, a in enumerate(items):
        for b in items[idx + 1:]:
            if not _capsule_pairable(a.category, b.category):
                continue
            checked += 1
            expected, _, _ = score_pair(a, b, None)
            assert cached[frozenset((a.id, b.id))] == pytest.approx(expected)
    assert checked > 0


def test_second_call_adds_no_rows(db):
    ensure_pair_scores(db, 1)
    first = db.query(ItemPairScore).count()
    ensure_pair_scores(db, 1)
    assert db.query(ItemPairScore).count() == first


def test_pairs_stored_canonically_once(db):
    ensure_pair_scores(db, 1)
    rows = db.query(ItemPairScore).all()
    assert all(r.item_a_id < r.item_b_id for r in rows)
    assert len({(r.item_a_id, r.item_b_id) for r in rows}) == len(rows)


def test_invalidate_item_drops_only_that_items_pairs(db):
    ensure_pair_scores(db, 1)
    total = db.query(ItemPairScore).count()
    removed = invalidate_item(db, 1)
    db.commit()
    assert removed > 0
    assert db.query(ItemPairScore).count() == total - removed
    # nothing left referencing it, in either column
    assert db.query(ItemPairScore).filter(
        (ItemPairScore.item_a_id == 1) | (ItemPairScore.item_b_id == 1)
    ).count() == 0
    ensure_pair_scores(db, 1)
    assert db.query(ItemPairScore).count() == total


def test_recolouring_an_item_changes_its_cached_score(db):
    """The stale-cache bug this exists to prevent: edit an item, get a new score."""
    before = ensure_pair_scores(db, 1)[frozenset((1, 3))]
    item = db.query(ClothingItem).filter(ClothingItem.id == 1).first()
    item.color = "orange"
    invalidate_item(db, 1)
    db.commit()
    after = ensure_pair_scores(db, 1)[frozenset((1, 3))]
    expected, _, _ = score_pair(item, db.query(ClothingItem).filter(ClothingItem.id == 3).first(), None)
    assert after == pytest.approx(expected)
    assert after != before


def test_invalidate_user_clears_everything(db):
    ensure_pair_scores(db, 1)
    assert db.query(ItemPairScore).count() > 0
    invalidate_user(db, 1)
    db.commit()
    assert db.query(ItemPairScore).count() == 0
