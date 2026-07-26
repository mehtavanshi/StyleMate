"""Regressions for the two 500s behind "Style Match Suggestions".

1. score_pair memoised on an unhashable stand-in (_HypotheticalItem is a
   dataclass with eq=True, so __hash__ is None) -> TypeError.
2. _MATCHING_CATEGORIES pairs footwear/accessory with "dress", but section_map
   had no "dress" bucket -> KeyError for every footwear and accessory item.
"""

from dataclasses import dataclass

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ClothingItem, User
from app.pairing_engine import score_pair, _score_pair_uncached
from app.style_match import _MATCHING_CATEGORIES, generate_style_match


@dataclass(eq=True)
class _Unhashable:
    """Mirrors _HypotheticalItem: eq=True means __hash__ is None."""
    id: int = 999
    category: str = "bottom"
    color: str = "navy"
    pattern: str = None
    occasion_tag: str = None
    season: str = None
    formality_score: int = None
    target_gender: str = None
    fabric_type: str = None
    fit_type: str = None
    sleeve_length: str = None
    embedding_json: str = None
    style_tags: str = None
    embellishments: str = None
    garment_length: str = None


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, name="T", email="t@example.com"))
    rows = [("top", "black"), ("bottom", "blue"), ("footwear", "white"),
            ("accessory", "brown"), ("dress", "navy"), ("outerwear", "grey")]
    for i, (cat, color) in enumerate(rows, start=1):
        session.add(ClothingItem(id=i, user_id=1, name=f"{cat}{i}",
                                 category=cat, color=color, occasion_tag="casual"))
    session.commit()
    yield session
    session.close()


def test_score_pair_accepts_unhashable_item(db):
    """The memo must not require its operands to be hashable."""
    real = db.query(ClothingItem).filter(ClothingItem.id == 1).first()
    hypo = _Unhashable()
    with pytest.raises(TypeError):
        hash(hypo)  # guard: this test is meaningless if it becomes hashable
    assert score_pair(real, hypo) == _score_pair_uncached(real, hypo)
    assert score_pair(hypo, real) == _score_pair_uncached(hypo, real)


@pytest.mark.parametrize("category", sorted(_MATCHING_CATEGORIES))
def test_every_partner_category_has_a_bucket(category):
    """Any category reachable as a partner must not blow up on lookup."""
    section_map = {"top": [], "bottom": [], "footwear": [], "accessory": [], "outerwear": []}
    for partner in _MATCHING_CATEGORIES[category]:
        section_map.setdefault(partner, []).append("x")  # must not raise


@pytest.mark.parametrize("item_id,category", [(1, "top"), (2, "bottom"), (3, "footwear"),
                                              (4, "accessory"), (5, "dress"), (6, "outerwear")])
def test_style_match_succeeds_for_every_category(db, item_id, category):
    result = generate_style_match(item_id, db)
    assert result.selected_item["category"] == category


def test_a_section_never_mixes_owned_with_invented(db):
    """The bug: catalogue inventions shown alongside/instead of real matches.

    A section is either the wardrobe's own matches, or — only when the wardrobe
    offers nothing above MATCH_THRESHOLD — invented fallbacks. Never both, so an
    invented item can never outrank something already hanging in the closet.
    """
    result = generate_style_match(1, db)
    for section in (result.matching_bottoms, result.matching_tops,
                    result.matching_footwear, result.matching_accessories,
                    result.layering_suggestions):
        if not section:
            continue
        owned = {x.owned for x in section}
        assert len(owned) == 1, (
            "section mixes owned and invented: "
            + ", ".join(f"{x.name}(owned={x.owned})" for x in section)
        )
        if section[0].owned:
            assert all(x.item_id is not None for x in section)


def test_owned_matches_are_preferred_when_they_exist(db):
    """Anything scoring above threshold in the wardrobe must reach its section."""
    result = generate_style_match(1, db)
    by_cat: dict[str, list] = {}
    for m in result.wardrobe_matches:
        by_cat.setdefault(m.category, []).append(m)
    sections = {
        "bottom": result.matching_bottoms,
        "footwear": result.matching_footwear,
        "accessory": result.matching_accessories,
        "outerwear": result.layering_suggestions,
    }
    for cat, owned_matches in by_cat.items():
        if cat not in sections:
            continue
        shown = sections[cat]
        assert shown and shown[0].owned, f"{cat}: owned match exists but section shows inventions"
        assert shown[0].match_percentage == max(m.match_percentage for m in owned_matches)


def test_shopping_suggestions_never_offer_something_already_owned(db):
    result = generate_style_match(1, db)
    owned_names = {i.name.lower() for i in db.query(ClothingItem).all()}
    for s in result.shopping_suggestions:
        assert s["owned"] is False
        assert s["item_name"].lower() not in owned_names


def test_generated_items_still_fill_an_empty_category(db):
    """Fallback must survive: a wardrobe with nothing to offer still suggests."""
    # Strip everything except the selected top, so no owned partner exists.
    db.query(ClothingItem).filter(ClothingItem.id != 1).delete(synchronize_session=False)
    db.commit()
    result = generate_style_match(1, db)
    filled = result.matching_bottoms + result.matching_footwear
    assert filled, "empty wardrobe should fall back to generated suggestions"
    assert all(not x.owned for x in filled)
