from __future__ import annotations

TAXONOMY: dict[str, dict[str, list[str]]] = {
    "bottom": {
        "jeans_pants": [
            "skinny", "straight_leg", "bootcut", "flare",
            "wide_leg", "baggy_mom", "boyfriend", "barrel_leg",
        ],
        "skirts": [
            "mini_skirt", "midi_skirt", "maxi_skirt",
            "a_line_skirt", "pencil_skirt", "pleated_skirt", "wrap_skirt",
        ],
        "other": [
            "shorts", "biker_shorts", "palazzo", "culottes",
            "joggers", "cargo_pants", "trousers",
        ],
    },
    "top": {
        "top_styles": [
            "crop_top", "regular_top", "waist_length_top", "tunic",
            "maxi_top", "peplum_top", "off_shoulder_top", "tube_top", "halter_top",
        ],
    },
    "kurti": {
        "kurti_styles": [
            "kurti_short", "kurti_long", "anarkali",
            "saree", "lehenga", "salwar_kameez", "palazzo_suit",
        ],
    },
    "accessory": {
        "ethnic": [
            "bangles", "jhumkas", "maang_tikka", "potli_bag",
            "juttis", "nose_ring", "waist_belt", "dupatta",
        ],
    },
}

_label_to_group: dict[str, str] = {}
for _cat, _groups in TAXONOMY.items():
    for _group, _labels in _groups.items():
        for _lbl in _labels:
            _label_to_group[_lbl] = _group


def get_subcategory_group(label: str) -> str | None:
    return _label_to_group.get(label)


def get_subcategory_labels(category: str) -> list[str]:
    groups = TAXONOMY.get(category, {})
    return [lbl for group_labels in groups.values() for lbl in group_labels]


def get_group_labels(category: str, group: str) -> list[str]:
    return TAXONOMY.get(category, {}).get(group, [])


def get_group_names(category: str) -> list[str]:
    return list(TAXONOMY.get(category, {}).keys())


EMBELLISHMENTS: list[str] = [
    "ribbon", "bow", "sequins", "lace", "tassel",
    "mirror_work", "buttons", "fringe", "beads",
]

EMBELLISHMENT_DISPLAY: dict[str, str] = {
    "ribbon": "ribbon trim",
    "bow": "bow detail",
    "sequins": "sequin embellishment",
    "lace": "lace detail",
    "tassel": "tassel fringe",
    "mirror_work": "mirror work embroidery",
    "buttons": "decorative buttons",
    "fringe": "fringe trim",
    "beads": "bead embellishment",
}

EMBELLISHMENT_THRESHOLD: float = 0.24

EMBELLISHMENT_POSITIVE_TEMPLATE = "a photo of a garment with {phrase}"
EMBELLISHMENT_NEGATIVE_TEMPLATE = "a photo of a plain garment with no {phrase}"

GARMENT_LENGTHS: list[str] = [
    "cropped", "waist", "hip", "knee", "midi", "ankle", "floor",
]

# ── Silhouette balance rules ──
# Maps a bottom subcategory to a list of top subcategories that create a
# balanced silhouette together.  Loose/wide bottoms pair with fitted/cropped
# tops; fitted/skinny bottoms pair with relaxed/tunic/maxi tops.
# Key: bottom subcategory label.  Value: compatible top subcategory labels.

SILHOUETTE_RULES: dict[str, list[str]] = {
    # Loose / wide bottoms → fitted / cropped tops
    "wide_leg": [
        "crop_top", "waist_length_top", "peplum_top",
        "off_shoulder_top", "tube_top", "halter_top", "regular_top",
    ],
    "baggy_mom": [
        "crop_top", "waist_length_top", "peplum_top",
        "off_shoulder_top", "tube_top", "halter_top",
    ],
    "flare": [
        "crop_top", "waist_length_top", "peplum_top",
        "off_shoulder_top", "tube_top", "halter_top",
    ],
    "bootcut": [
        "crop_top", "waist_length_top", "peplum_top",
        "off_shoulder_top", "tube_top", "halter_top",
    ],
    "barrel_leg": [
        "crop_top", "waist_length_top", "peplum_top",
        "tube_top", "halter_top",
    ],
    "palazzo": [
        "crop_top", "waist_length_top", "peplum_top",
        "tube_top", "halter_top",
    ],
    "maxi_skirt": [
        "crop_top", "waist_length_top", "peplum_top",
        "tube_top", "halter_top",
    ],
    "a_line_skirt": [
        "crop_top", "waist_length_top", "peplum_top",
        "tube_top", "halter_top",
    ],
    "culottes": [
        "crop_top", "waist_length_top", "peplum_top",
        "halter_top", "tube_top",
    ],
    "joggers": [
        "crop_top", "waist_length_top", "peplum_top",
        "tube_top", "halter_top",
    ],
    "cargo_pants": [
        "crop_top", "waist_length_top", "peplum_top",
        "off_shoulder_top", "tube_top", "halter_top",
    ],
    "mini_skirt": [
        "regular_top", "tunic", "maxi_top",
        "peplum_top", "off_shoulder_top",
    ],
    # Fitted / skinny bottoms → relaxed / tunic / maxi tops
    "skinny": [
        "tunic", "maxi_top", "peplum_top",
        "off_shoulder_top", "regular_top",
    ],
    "straight_leg": [
        "tunic", "maxi_top", "peplum_top",
        "off_shoulder_top", "regular_top",
    ],
    "pencil_skirt": [
        "tunic", "maxi_top", "peplum_top",
        "off_shoulder_top", "regular_top",
    ],
    "trousers": [
        "tunic", "maxi_top", "regular_top", "peplum_top",
    ],
    "shorts": [
        "tunic", "maxi_top", "regular_top",
        "off_shoulder_top", "crop_top",
    ],
    "biker_shorts": [
        "tunic", "maxi_top", "regular_top", "off_shoulder_top",
    ],
    "wrap_skirt": [
        "tunic", "maxi_top", "peplum_top",
        "off_shoulder_top", "regular_top",
    ],
    "midi_skirt": [
        "tunic", "maxi_top", "peplum_top",
        "off_shoulder_top", "regular_top",
    ],
    "pleated_skirt": [
        "tunic", "maxi_top", "peplum_top",
        "off_shoulder_top", "regular_top",
    ],
}

# ── Embellishment coordination config ──

EMBELLISHMENT_MATCH_BONUS = 0.90
EMBELLISHMENT_PLAIN_BOOST = 0.60

# ── Wear family (ethnic vs western) ──

WEAR_FAMILY_DEFAULTS: dict[str, str] = {
    "kurti": "ethnic",
    "top": "western",
    "bottom": "western",
    "dress": "western",
    "outerwear": "western",
    "footwear": "western",
    "accessory": "western",
}

WEAR_FAMILY_SUBCATEGORY_OVERRIDES: dict[str, str] = {
    "saree": "ethnic",
    "lehenga": "ethnic",
    "salwar_kameez": "ethnic",
    "anarkali": "ethnic",
    "kurti_short": "ethnic",
    "kurti_long": "ethnic",
    "palazzo_suit": "ethnic",
    "dupatta": "ethnic",
    "juttis": "ethnic",
    "bangles": "ethnic",
    "jhumkas": "ethnic",
    "maang_tikka": "ethnic",
    "potli_bag": "ethnic",
}


# ── Anchor vs variant roles for outfit deduplication ──
# Anchor pieces define an outfit's identity; swapping only a variant
# (e.g. different shoes with the same top+bottom) should not produce a
# distinct cached outfit entry. Only the highest-scoring combination of
# variants is kept per unique set of anchor items.

ANCHOR_ROLES: set[str] = {"top", "bottom", "dress", "kurti", "saree"}
VARIANT_ROLES: set[str] = {"footwear", "accessory", "outerwear"}


def get_wear_family(category: str | None, subcategory: str | None) -> str | None:
    if not category:
        return None
    if subcategory:
        override = WEAR_FAMILY_SUBCATEGORY_OVERRIDES.get(subcategory)
        if override is not None:
            return override
    return WEAR_FAMILY_DEFAULTS.get(category)
