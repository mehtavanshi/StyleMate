from app.pairing_engine import (
    _color_to_hsl,
    _hue_diff,
    _is_neutral_hsl,
    score_outfit,
    score_pair,
    score_pair_color,
)


class MockItem:
    """Minimal stand-in for ClothingItem used in scoring tests."""

    def __init__(
        self,
        category,
        color=None,
        pattern=None,
        occasion_tag=None,
        formality=None,
        target_gender=None,
        embedding_json=None,
    ):
        self.id = 0
        self.category = category
        self.color = color
        self.pattern = pattern
        self.name = None
        self.image_url = None
        self.occasion_tag = occasion_tag
        self.formality = formality
        self.target_gender = target_gender
        self.embedding_json = embedding_json


class TestPairColor:
    def test_navy_plus_white_scores_high(self):
        assert score_pair_color("navy", "white") >= 0.85

    def test_red_plus_orange_adjacent_warm(self):
        assert score_pair_color("red", "orange") >= 0.70

    def test_red_plus_violet_clashing(self):
        assert score_pair_color("red", "violet") <= 0.40

    def test_navy_plus_orange_complementary(self):
        assert score_pair_color("navy", "orange") >= 0.40

    def test_white_plus_navy_symmetry(self):
        assert score_pair_color("white", "navy") >= 0.85

    def test_missing_color_returns_mid(self):
        assert score_pair_color(None, "red") == 0.5
        assert score_pair_color(None, None) == 0.5

    def test_neutral_with_anything_scores_high(self):
        for neutral in ["black", "white", "beige", "grey", "navy"]:
            assert score_pair_color(neutral, "red") >= 0.85
            assert score_pair_color("red", neutral) >= 0.85


class TestScoreOutfit:
    def test_neutral_top_with_bright_bottom(self):
        top = MockItem("top", "white")
        bottom = MockItem("bottom", "red")
        score, reason = score_outfit([top, bottom])
        assert score >= 0.7
        assert isinstance(reason, str)

    def test_analogous_outfit(self):
        top = MockItem("top", "red")
        bottom = MockItem("bottom", "orange")
        score, reason = score_outfit([top, bottom])
        assert score >= 0.7
        assert "analogous" in reason

    def test_clashing_patterns_penalised(self):
        top = MockItem("top", "red", pattern="striped")
        bottom = MockItem("bottom", "yellow", pattern="checked")
        score, _ = score_outfit([top, bottom])
        assert score < 0.5

    def test_empty_outfit(self):
        score, reason = score_outfit([])
        assert score == 0.0
        assert reason == "Empty outfit"


class TestHSLHelpers:
    def test_color_to_hsl_known(self):
        hsl = _color_to_hsl("navy")
        assert hsl is not None
        assert hsl[0] == 220

    def test_color_to_hsl_unknown(self):
        assert _color_to_hsl(None) is None
        assert _color_to_hsl("") is None

    def test_is_neutral_white(self):
        assert _is_neutral_hsl((0, 0, 100), "white") is True

    def test_is_neutral_low_saturation(self):
        assert _is_neutral_hsl((120, 10, 50), "muted green") is True

    def test_hue_diff_symmetric(self):
        assert _hue_diff(10, 350) == 20
        assert _hue_diff(350, 10) == 20


class TestScorePair:
    def test_gender_mismatch_scores_zero(self):
        a = MockItem("top", "white", target_gender="men")
        b = MockItem("bottom", "navy", target_gender="women")
        score, reason = score_pair(a, b)
        assert score == 0.0
        assert "mismatch" in reason

    def test_matching_occasion_formality_boosts_score(self):
        good = MockItem("top", "white", occasion_tag="formal", formality="business")
        well = MockItem("bottom", "navy", occasion_tag="formal", formality="business")
        bad = MockItem("bottom", "navy", occasion_tag="casual", formality="casual")
        score_high, _ = score_pair(good, well)
        score_low, _ = score_pair(good, bad)
        assert score_high > score_low

    def test_similar_embeddings_boost_score(self):
        import json

        vec_a = [1.0] + [0.0] * 511
        vec_b = [1.0] + [0.0] * 511  # identical
        vec_c = [0.0, 1.0] + [0.0] * 510  # orthogonal

        similar = MockItem(
            "top", "white", embedding_json=json.dumps(vec_a),
        )
        same_style = MockItem(
            "bottom", "navy", embedding_json=json.dumps(vec_b),
        )
        diff_style = MockItem(
            "bottom", "navy", embedding_json=json.dumps(vec_c),
        )

        score_similar, _ = score_pair(similar, same_style)
        score_diff, _ = score_pair(similar, diff_style)
        assert score_similar > score_diff
