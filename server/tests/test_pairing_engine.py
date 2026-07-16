from app.pairing_engine import (
    _is_complementary,
    _is_neutral,
    _same_family,
    score_outfit,
    score_pair_color,
)


class MockItem:
    """Minimal stand-in for ClothingItem used in scoring tests."""

    def __init__(self, category, color=None, pattern=None):
        self.id = 0
        self.category = category
        self.color = color
        self.pattern = pattern
        self.name = None
        self.image_url = None


class TestPairColor:
    def test_neutral_with_anything_scores_high(self):
        for neutral in ["black", "white", "beige", "grey", "navy"]:
            assert score_pair_color(neutral, "red") >= 0.85
            assert score_pair_color("red", neutral) >= 0.85

    def test_same_family_scores_high(self):
        assert score_pair_color("red", "burgundy") >= 0.75
        assert score_pair_color("sky blue", "navy") >= 0.75

    def test_complementary_scores_well(self):
        score = score_pair_color("red", "green")
        assert score >= 0.7

    def test_random_bright_pair_low(self):
        score = score_pair_color("red", "yellow")
        assert score <= 0.5

    def test_missing_color_returns_mid(self):
        assert score_pair_color(None, "red") == 0.5
        assert score_pair_color(None, None) == 0.5


class TestScoreOutfit:
    def test_neutral_top_with_bright_bottom(self):
        top = MockItem("top", "white")
        bottom = MockItem("bottom", "red")
        score, reason = score_outfit([top, bottom])
        assert score >= 0.7
        assert isinstance(reason, str)

    def test_monochrome_outfit(self):
        top = MockItem("top", "navy")
        bottom = MockItem("bottom", "sky blue")
        shoe = MockItem("footwear", "royal blue")
        score, reason = score_outfit([top, bottom, shoe])
        assert score >= 0.7
        assert "monochrome" in reason

    def test_clashing_patterns_penalised(self):
        top = MockItem("top", "red", pattern="striped")
        bottom = MockItem("bottom", "yellow", pattern="checked")
        score, _ = score_outfit([top, bottom])
        assert score < 0.5

    def test_empty_outfit(self):
        score, reason = score_outfit([])
        assert score == 0.0
        assert reason == "Empty outfit"
