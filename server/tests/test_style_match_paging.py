"""Load More must return items the shallow page did not already show.

Guards the failure this replaced: templates are only 2-5 per category, so a
deeper `limit` returned the exact same list and "Load More" showed nothing new.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ClothingItem, User
from app.style_match import (
    MAX_CANDIDATES_PER_CATEGORY,
    _candidate_combos,
    generate_style_match,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, name="T", email="t@example.com"))
    session.add(
        ClothingItem(id=1, user_id=1, name="tee", category="top", color="pink",
                     occasion_tag="casual")
    )
    session.commit()
    yield session
    session.close()


def _shop_names(result):
    return [s["item_name"] for s in result.shopping_suggestions]


def test_deeper_limit_adds_new_suggestions(db):
    shallow = generate_style_match(1, db, limit=2)
    deep = generate_style_match(1, db, limit=12)

    shallow_names, deep_names = _shop_names(shallow), _shop_names(deep)
    assert len(deep_names) > len(shallow_names), "deeper page returned nothing new"
    assert set(deep_names) - set(shallow_names), "deeper page repeated the same items"


def test_no_duplicate_shopping_suggestions(db):
    names = _shop_names(generate_style_match(1, db, limit=20))
    assert len(names) == len(set(names))


def test_default_limit_unchanged(db):
    default = generate_style_match(1, db)
    explicit = generate_style_match(1, db, limit=MAX_CANDIDATES_PER_CATEGORY)
    assert _shop_names(default) == _shop_names(explicit)


def test_combos_expand_only_colorable_templates():
    rotation = ["black", "olive", "navy"]
    templates = [
        {"name": "{color} Chinos"},          # colour placeholder -> expands
        {"name": "White Sneakers"},          # no placeholder -> one variant
        {"name": "{color} Tote", "color": "beige"},  # fixed colour -> one variant
    ]
    combos = _candidate_combos(templates, rotation, count=10)
    names = [(i, t["name"], c) for i, t, c in combos]

    chinos = [c for i, n, c in names if n == "{color} Chinos"]
    assert len(chinos) == len(set(chinos)) > 1, "colourable template did not expand"
    assert sum(1 for _, n, _ in names if n == "White Sneakers") == 1
    assert [c for _, n, c in names if n == "{color} Tote"] == ["beige"]


def test_combos_respect_count_headroom():
    rotation = ["black", "olive", "navy", "beige", "grey"]
    templates = [{"name": "{color} Jeans"}, {"name": "{color} Skirt"}]
    assert len(_candidate_combos(templates, rotation, count=2)) <= 4
