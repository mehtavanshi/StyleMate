"""Regression checks for the logic bugs fixed in the audit pass."""

from types import SimpleNamespace

from app.pairing_engine import (
    _body_type_style_score,
    _color_to_hsl,
    score_outfit,
    score_pair_color,
)
from app.services.weather_service import TEMP_RULES, rule_for_temp


def _item(**kw):
    base = dict(
        id=0, category=None, subcategory=None, color=None, pattern=None,
        style_tags=None, embellishments=None, fabric_type=None, fit_type=None,
        season=None, occasion_tag=None, formality_score=None,
        target_gender=None, embedding_json=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_rule_for_temp_always_returns_a_rule():
    # Inside the covered range.
    assert rule_for_temp(25)["season"] == "summer"
    # Outside every range — used to return the range bound (a float).
    for temp in (999.0, -999.0, float("nan")):
        rule = rule_for_temp(temp)
        assert isinstance(rule, dict), temp
        assert "season" in rule and "fabrics" in rule


def test_temp_rules_shape():
    for low, high, rule in TEMP_RULES:
        assert low < high
        assert isinstance(rule, dict)


def test_multiword_colors_resolve_to_the_specific_shade():
    # "navy blue" used to match "blue" first, "olive green" used to match
    # "green" — both are visibly different colors.
    assert _color_to_hsl("navy blue") == _color_to_hsl("navy")
    assert _color_to_hsl("olive green") == _color_to_hsl("olive")
    assert _color_to_hsl("sky blue") == _color_to_hsl("sky blue")
    assert _color_to_hsl("navy blue") != _color_to_hsl("blue")


def test_unknown_color_is_none():
    assert _color_to_hsl("kryptonite") is None
    assert _color_to_hsl(None) is None


def test_repeated_whitespace_normalises():
    # "navy  blue" used to miss the lookup that "navy blue" hits.
    assert _color_to_hsl("  Navy   Blue ") == _color_to_hsl("navy blue")


def test_neutral_clashes_are_still_penalised():
    # Both neutrals: the neutral shortcut used to return a confident 0.9.
    assert score_pair_color("navy", "black") == 0.25
    assert score_pair_color("brown", "black") == 0.25
    # A neutral with a non-clashing colour still pairs well.
    assert score_pair_color("beige", "green") == 0.9


def test_body_type_boost_never_scores_below_neutral():
    tagged = _item(style_tags='["belted"]')
    unmatched = _item(style_tags='["asymmetric"]')
    untagged = _item()
    # A tag with no rule for this body type is neutral, not a penalty.
    assert _body_type_style_score(unmatched, "rectangle") == 0.5
    assert _body_type_style_score(untagged, "rectangle") == 0.5
    # A tag the body type favours scores above neutral.
    assert _body_type_style_score(tagged, "rectangle") > 0.5


def test_colour_harmony_bonuses_do_not_stack():
    # Complementary and analogous are mutually exclusive readings; only one
    # bonus may ever apply, and the score stays inside [0, 1].
    outfit = [
        _item(id=1, category="top", color="blue"),
        _item(id=2, category="bottom", color="orange"),
    ]
    score, reason, _ = score_outfit(outfit)
    assert 0.0 <= score <= 1.0
    assert "complementary" not in reason or "analogous" not in reason


def test_all_neutral_palette_affects_the_score():
    neutral = [
        _item(id=1, category="top", color="beige"),
        _item(id=2, category="bottom", color="cream"),
    ]
    coloured = [
        _item(id=1, category="top", color="beige"),
        _item(id=2, category="bottom", color="teal"),
    ]
    n_score, n_reason, _ = score_outfit(neutral)
    c_score, _, _ = score_outfit(coloured)
    assert "all-neutral palette" in n_reason
    # The detection used to be reported but never scored.
    assert n_score > c_score


def test_unmappable_colours_are_not_called_all_neutral():
    outfit = [
        _item(id=1, category="top", color="kryptonite"),
        _item(id=2, category="bottom", color="kryptonite"),
    ]
    _, reason, _ = score_outfit(outfit)
    assert "all-neutral palette" not in reason


def test_single_item_and_empty_share_a_baseline():
    assert score_outfit([])[0] == score_outfit([_item(id=1, category="top")])[0]
