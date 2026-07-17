"""Config-driven body-type styling rules.

Loads and validates ``config/body_type_rules.yaml`` at startup so a
malformed file causes an immediate, loud failure instead of silently
breaking scoring at runtime.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, field_validator, model_validator

logger = logging.getLogger(__name__)

VALID_BODY_TYPES = {
    "rectangle",
    "hourglass",
    "pear",
    "apple",
    "inverted_triangle",
}


class StyleTagRule(BaseModel):
    tag: str
    boost: float

    @field_validator("boost")
    @classmethod
    def boost_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"boost must be between 0.0 and 1.0, got {v}")
        return v

    @field_validator("tag")
    @classmethod
    def tag_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("tag must not be empty")
        return v.strip().lower()


class BodyTypeRules(BaseModel):
    rectangle: list[StyleTagRule]
    hourglass: list[StyleTagRule]
    pear: list[StyleTagRule]
    apple: list[StyleTagRule]
    inverted_triangle: list[StyleTagRule]

    @model_validator(mode="after")
    def each_body_type_has_rules(self) -> BodyTypeRules:
        for body_type in VALID_BODY_TYPES:
            rules = getattr(self, body_type)
            if not rules:
                raise ValueError(
                    f"body_type '{body_type}' must have at least one rule"
                )
        return self


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "body_type_rules.yaml"

_body_type_rules: BodyTypeRules | None = None


def load_body_type_rules(path: Path | None = None) -> BodyTypeRules:
    """Load and validate the body-type rules YAML config.

    Raises pydantic.ValidationError on malformed config and
    FileNotFoundError / yaml.YAMLError on file issues.
    """
    global _body_type_rules

    p = path or CONFIG_PATH
    if not p.exists():
        raise FileNotFoundError(f"Body-type rules config not found: {p}")

    with open(p, "r") as f:
        raw = yaml.safe_load(f)

    _body_type_rules = BodyTypeRules.model_validate(raw)
    logger.info(
        "Loaded body-type rules: %s",
        {bt: len(rules) for bt, rules in _body_type_rules.model_dump().items()},
    )
    return _body_type_rules


def get_body_type_rules() -> BodyTypeRules:
    """Return the cached body-type rules, loading from disk on first call."""
    global _body_type_rules
    if _body_type_rules is None:
        _body_type_rules = load_body_type_rules()
    return _body_type_rules


def get_style_boost(body_type: str, tag: str) -> float:
    """Return the boost value for a style tag under a given body type.

    Returns 0.0 if the body type is unknown or the tag has no rule.
    """
    rules = get_body_type_rules()
    bt = body_type.strip().lower()
    lookup = rules.model_dump()
    for rule in lookup.get(bt, []):
        if rule["tag"] == tag.strip().lower():
            return rule["boost"]
    return 0.0
