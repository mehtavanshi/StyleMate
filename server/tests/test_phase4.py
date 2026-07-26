"""Phase 4 logic checks — the parts that break silently if the rules drift.

No Gemini, no weather API, no network: every AI path here is exercised through
its documented fallback so the suite runs offline.
"""

from datetime import date, timedelta
from types import SimpleNamespace

from app.pairing_engine import _capsule_pairable, _count_outfits
from app.services.calendar_service import (
    REPEAT_WARNING_THRESHOLD,
    check_outfit_repeat,
    get_item_wear_history,
)
from app.services.nlp_router import _fallback_params
from app.services.packing_service import _clean_groups, _fallback_groups
from app.services.weather_service import filter_items_by_weather, rule_for_temp


def _item(item_id, category, season=None, color="black"):
    return SimpleNamespace(id=item_id, category=category, season=season, color=color)


# ── 4.6 capsule counting ──


def test_capsule_pairable_is_symmetric_and_rejects_same_category():
    assert _capsule_pairable("top", "bottom")
    assert _capsule_pairable("bottom", "top")
    assert not _capsule_pairable("top", "top")
    assert not _capsule_pairable("footwear", "outerwear")


def test_count_outfits_needs_every_pair_to_be_good():
    top, bottom, shoe = _item(1, "top"), _item(2, "bottom"), _item(3, "footwear")
    items = [top, bottom, shoe]

    all_good = {frozenset((1, 2)), frozenset((1, 3)), frozenset((2, 3))}
    # top+bottom, plus top+bottom+shoe
    assert _count_outfits(items, all_good) == 2

    # Shoe clashes with the bottom → the 3-piece outfit must not count.
    assert _count_outfits(items, {frozenset((1, 2)), frozenset((1, 3))}) == 1

    # Top and bottom don't work together → nothing is buildable.
    assert _count_outfits(items, {frozenset((1, 3)), frozenset((2, 3))}) == 0


def test_count_outfits_counts_dresses_with_and_without_shoes():
    dress, shoe = _item(1, "dress"), _item(2, "footwear")
    assert _count_outfits([dress, shoe], {frozenset((1, 2))}) == 2
    assert _count_outfits([dress, shoe], set()) == 1  # dress alone still counts


# ── 4.4 weather filtering ──


def test_rule_for_temp_covers_the_whole_range():
    assert rule_for_temp(38)["season"] == "summer"
    assert rule_for_temp(25)["season"] == "summer"
    assert rule_for_temp(18)["season"] == "spring"
    assert rule_for_temp(10)["season"] == "fall"
    assert rule_for_temp(-5)["season"] == "winter"


def test_filter_drops_warm_layers_and_wrong_season():
    items = [
        _item(1, "top", "summer"),
        _item(2, "bottom", "summer"),
        _item(3, "footwear", "all-season"),
        _item(4, "outerwear", "winter"),
        _item(5, "top", "winter"),
    ]
    kept = filter_items_by_weather(items, 30.0)
    kept_ids = {i.id for i in kept}
    assert kept_ids == {1, 2, 3}, "winter top and outerwear should be dropped when hot"


def test_filter_returns_everything_rather_than_starving_the_engine():
    # Only one summer item: filtering would leave too little to build an outfit.
    items = [_item(1, "top", "summer"), _item(2, "bottom", "winter")]
    assert filter_items_by_weather(items, 32.0) == items


# ── 4.3 natural-language fallback ──


def test_fallback_params_reads_occasion_and_formality():
    params = _fallback_params("I have an interview tomorrow")
    assert params["occasion_tag"] == "office"
    assert params["formality_level"] == 4
    assert params["source"] == "keywords"


def test_fallback_params_returns_nulls_when_nothing_matches():
    params = _fallback_params("hello there")
    assert params["occasion_tag"] is None
    assert params["formality_level"] is None


# ── 4.5 packing group validation ──


def test_clean_groups_rejects_malformed_entries():
    assert _clean_groups("not a list") is None
    assert _clean_groups([{"category": "spaceship", "quantity": 2}]) is None
    assert _clean_groups([{"category": "top", "quantity": "four"}]) is None

    cleaned = _clean_groups([{"category": "TOP", "quantity": 99, "note": "x" * 100}])
    assert cleaned == [{"category": "top", "quantity": 7, "note": "x" * 60}]


def test_fallback_groups_scale_with_trip_length():
    short = {g["category"]: g["quantity"] for g in _fallback_groups(2, "leisure")}
    long = {g["category"]: g["quantity"] for g in _fallback_groups(10, "leisure")}
    assert long["top"] > short["top"]
    assert all(1 <= q <= 7 for q in long.values())
    assert "dress" in {g["category"] for g in _fallback_groups(5, "beach")}


# ── 4.8 wear tracking (in-memory sqlite) ──


def _wear_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.models import CalendarEntry, ClothingItem, User

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    db.add(User(id=1, name="Test", email="t@example.com"))
    db.add(ClothingItem(id=10, user_id=1, category="top", name="Worn top"))
    db.add(ClothingItem(id=11, user_id=1, category="top", name="Fresh top"))
    db.add(ClothingItem(id=12, user_id=1, category="bottom", name="Jeans"))

    # Item 10 locked on three separate recent days → over the warning threshold.
    for offset in (1, 3, 5):
        db.add(
            CalendarEntry(
                user_id=1, date=date.today() - timedelta(days=offset), locked_outfit_id=10
            )
        )
    # Old enough to fall outside the 30-day window.
    db.add(
        CalendarEntry(
            user_id=1, date=date.today() - timedelta(days=200), locked_outfit_id=11
        )
    )
    db.commit()
    return db


def test_wear_history_counts_only_the_window():
    db = _wear_db()
    history = get_item_wear_history(1, 30, db)
    assert history["total_wears"] == 3
    assert history["most_worn"][0]["id"] == 10
    assert history["most_worn"][0]["wear_count"] == 3
    # Item 11's only wear is 200 days old, so it reads as never worn.
    assert {i["id"] for i in history["never_worn"]} == {11, 12}


def test_repeat_check_warns_and_offers_a_less_worn_swap():
    db = _wear_db()
    result = check_outfit_repeat(1, [10, 12], db)
    assert len(result["warnings"]) == 1

    warning = result["warnings"][0]
    assert warning["item_id"] == 10
    assert warning["wear_count"] >= REPEAT_WARNING_THRESHOLD
    assert warning["alternative"]["id"] == 11, "swap must be same category, less worn"

    # A fresh outfit gets no warnings at all.
    assert check_outfit_repeat(1, [11, 12], db)["warnings"] == []
