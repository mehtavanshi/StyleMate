import base64
import json
import logging
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.retry import call_with_retry

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

router = APIRouter(tags=["tagging"])

# Primary tagging: local FashionCLIP (free, no rate limits).
# Secondary: Gemini free tier (~1,500 req/day), used only when TAGGING_PROVIDER=vision_api.
TAGGING_PROVIDER = os.environ.get("TAGGING_PROVIDER", "fashion_clip")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
GEMINI_API_URL = os.environ.get(
    "GEMINI_API_URL",
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
)

SYSTEM_PROMPT = (
    "Analyze this clothing item photo carefully. "
    "Return ONLY valid JSON (no markdown, no explanation) with these exact fields: "
    "category, subcategory (a more specific type within the category — "
    "for bottoms use one of: skinny, straight_leg, bootcut, flare, wide_leg, baggy_mom, "
    "boyfriend, barrel_leg, mini_skirt, midi_skirt, maxi_skirt, a_line_skirt, "
    "pencil_skirt, pleated_skirt, wrap_skirt, shorts, biker_shorts, palazzo, culottes, "
    "joggers, cargo_pants, trousers; "
    "for tops use one of: crop_top, regular_top, waist_length_top, tunic, maxi_top, "
    "peplum_top, off_shoulder_top, tube_top, halter_top; "
    "for kurti use one of: kurti_short, kurti_long, anarkali, saree, lehenga, "
    "salwar_kameez, palazzo_suit; "
    "for accessories use one of: bangles, jhumkas, maang_tikka, potli_bag, juttis, "
    "nose_ring, waist_belt; otherwise null), "
    "target_gender (men/women/unisex — default to unisex if the styling is "
    "ambiguous, do not guess), dominant_color, secondary_color (or null), pattern, "
    "fabric_type, fit_type, sleeve_length (or 'not_applicable'), "
    "garment_length (one of: cropped, waist, hip, knee, midi, ankle, floor, or null), "
    "embellishments (array of any that apply from: ribbon, bow, sequins, lace, tassel, "
    "mirror_work, buttons, fringe, beads — empty array if none), "
    "occasion_tag (one of: casual, office, ethnic, party, formal, loungewear), "
    "season (one of: spring, summer, fall, winter, all-season), "
    "formality_score (1-5). "
    "For each field also include a confidence value from 0 to 1 in a parallel "
    "'confidence' object using the same field names. "
    "Base every judgment strictly on visible details in the image — "
    "do not assume details you cannot see."
)

CANDIDATE_LABELS = {
    "category": ["top", "bottom", "kurti", "dress", "outerwear", "footwear", "accessory"],
    "pattern": ["solid", "striped", "printed", "checked"],
    "dominant_color": [
        "black", "white", "red", "blue", "navy", "green", "yellow",
        "orange", "pink", "purple", "brown", "grey", "beige",
    ],
    "occasion_tag": ["casual", "office", "ethnic", "party", "formal", "loungewear"],
    "season": ["spring", "summer", "fall", "winter", "all-season"],
    "fabric_type": ["cotton", "denim", "silk", "wool", "leather", "linen", "knit", "synthetic"],
    "fit_type": ["slim", "regular", "oversized", "loose"],
    "sleeve_length": ["sleeveless", "short", "three_quarter", "long", "not_applicable"],
}

# Override raw subcategory labels with more descriptive text for FashionCLIP
# zero-shot prompts, so ambiguous labels (e.g. "palazzo" = trouser vs suit
# co-ord) are distinguished without changing the stored internal key.
_SUBCATEGORY_DISPLAY_NAMES: dict[str, str] = {
    "palazzo": "palazzo trousers (wide-leg bottom)",
}

STYLE_TAG_CANDIDATES: list[str] = [
    "belted", "wrap_style", "structured", "flowy", "cropped",
    "high_waisted", "fitted", "a_line", "v_neck", "empire_waist",
    "wide_leg", "asymmetric", "peplum", "ruffled", "scoop_neck",
]

FORMALITY_MAP = {
    "loungewear": 1,
    "casual": 2,
    "office": 3,
    "party": 4,
    "formal": 5,
    "ethnic": 4,
}


class TagItemRequest(BaseModel):
    image_url: str


SERVER_DIR = Path(__file__).resolve().parents[2]

MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _read_image(image_url: str) -> tuple[bytes, str]:
    if image_url.startswith("/"):
        path = Path(image_url)
        if not path.exists():
            path = SERVER_DIR / image_url.lstrip("/")
        ext = path.suffix.lower()
        content_type = MIME_MAP.get(ext, "image/jpeg")
        with open(path, "rb") as f:
            return f.read(), content_type
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(image_url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/jpeg")
        return resp.content, content_type


def _call_vision_api(image_url: str) -> str:
    # Gemini free tier is rate-limited to ~1,500 req/day.
    # FashionCLIP (local) should remain the primary tagging method.
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")

    image_data, content_type = _read_image(image_url)
    b64 = base64.b64encode(image_data).decode()

    api_url = GEMINI_API_URL.replace("{model}", GEMINI_MODEL)

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": SYSTEM_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": content_type.split(";")[0],
                            "data": b64,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 500,
        },
    }

    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=60.0) as client:
        resp = call_with_retry(lambda: client.post(api_url, json=payload, headers=headers))
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


def _parse_tags(raw: str) -> dict:
    """Parse Gemini's JSON response, extracting tags and confidence."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    data = json.loads(text)
    required = {"category", "dominant_color", "pattern", "occasion_tag", "season"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    confidence_raw = data.pop("confidence", {}) or {}
    # Drop secondary_color — not stored in our model.
    data.pop("secondary_color", None)

    # Normalize embellishments: Gemini returns a list, store as JSON string.
    if "embellishments" in data and isinstance(data["embellishments"], list):
        data["embellishments"] = json.dumps(data["embellishments"])

    return {"tags": data, "confidence": confidence_raw}


def _tag_item_vision_api(image_url: str) -> dict:
    try:
        parsed = _parse_tags(_call_vision_api(image_url))
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Gemini API error: status=%s body=%s provider=%s",
            exc.response.status_code,
            exc.response.text[:500],
            GEMINI_API_URL,
            exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Gemini API error: {exc.response.status_code}",
        )
    except Exception as exc:
        logger.error("AI tagging failed for provider=%s: %s", GEMINI_API_URL, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI tagging failed: {exc}")

    from app.style_embeddings import CONFIDENCE_THRESHOLD

    raw_tags = parsed["tags"]
    raw_conf = parsed["confidence"]

    tags: dict[str, str | int | None] = {}
    confidence: dict[str, float] = {}
    needs_review: dict[str, bool] = {}

    for field in raw_tags:
        conf = float(raw_conf.get(field, 1.0))
        confidence[field] = conf
        if conf < CONFIDENCE_THRESHOLD:
            tags[field] = None
            needs_review[field] = True
        else:
            tags[field] = raw_tags[field]
            needs_review[field] = False

    # Derive formality_score from occasion_tag (consistent with FashionCLIP path).
    occasion = tags.get("occasion_tag")
    if occasion:
        formality_score = FORMALITY_MAP.get(occasion, 3)
        if occasion not in FORMALITY_MAP:
            logger.info("FALLBACK: occasion=%r not in FORMALITY_MAP, using formality=3", occasion)
    else:
        formality_score = 3
        logger.info("FALLBACK: occasion_tag is None, using formality=3")
    tags["formality_score"] = formality_score
    confidence["formality_score"] = 1.0
    needs_review["formality_score"] = False

    result = {**tags, "_confidence": confidence, "_needs_review": needs_review}
    logger.info("Gemini tags: %s", {k: v for k, v in tags.items() if k != "_confidence"})
    return result


def _tag_item_fashion_clip(image_url: str) -> dict:
    from app.style_embeddings import (
        CONFIDENCE_THRESHOLD,
        classify_target_gender,
        zero_shot_binary_check,
        zero_shot_classify,
    )
    from app.fashion_taxonomy import (
        EMBELLISHMENT_NEGATIVE_TEMPLATE,
        EMBELLISHMENT_POSITIVE_TEMPLATE,
        EMBELLISHMENT_THRESHOLD,
        EMBELLISHMENTS,
        EMBELLISHMENT_DISPLAY,
        GARMENT_LENGTHS,
        get_group_labels,
        get_group_names,
        get_subcategory_labels,
    )

    tags: dict[str, str | int | None] = {}
    confidence: dict[str, float] = {}
    needs_review: dict[str, bool] = {}
    failures: list[str] = []

    for field, labels in CANDIDATE_LABELS.items():
        try:
            label, conf = zero_shot_classify(image_url, labels)
            confidence[field] = conf
            if conf < CONFIDENCE_THRESHOLD:
                tags[field] = None
                needs_review[field] = True
            else:
                tags[field] = label
                needs_review[field] = False
            logger.info(
                "FashionCLIP %s: %s (%.2f) needs_review=%s",
                field, label, conf, needs_review[field],
            )
        except Exception as exc:
            logger.warning("FashionCLIP field=%s failed: %s", field, exc)
            tags[field] = None
            confidence[field] = 0.0
            needs_review[field] = True
            failures.append(field)

    if len(failures) == len(CANDIDATE_LABELS):
        raise HTTPException(
            status_code=500,
            detail=f"FashionCLIP tagging failed for all fields: {failures}",
        )

    # ── Subcategory (two-stage: group → specific label) ──
    category = tags.get("category")
    if category and get_subcategory_labels(category):
        try:
            group_names = get_group_names(category)
            if len(group_names) == 1:
                group = group_names[0]
            else:
                group, group_conf = zero_shot_classify(image_url, group_names)
                if group_conf < CONFIDENCE_THRESHOLD:
                    tags["subcategory"] = None
                    confidence["subcategory"] = group_conf
                    needs_review["subcategory"] = True
                    group = None

            if group:
                labels = get_group_labels(category, group)
                display_labels = [_SUBCATEGORY_DISPLAY_NAMES.get(l, l) for l in labels]
                sub_label, sub_conf = zero_shot_classify(image_url, display_labels)
                reverse_map = {v: k for k, v in _SUBCATEGORY_DISPLAY_NAMES.items()}
                sub_label = reverse_map.get(sub_label, sub_label)
                confidence["subcategory"] = sub_conf
                if sub_conf < CONFIDENCE_THRESHOLD:
                    tags["subcategory"] = None
                    needs_review["subcategory"] = True
                else:
                    tags["subcategory"] = sub_label
                    needs_review["subcategory"] = False
                logger.info(
                    "FashionCLIP subcategory: %s (group=%s, %.2f) needs_review=%s",
                    sub_label, group, sub_conf, needs_review["subcategory"],
                )
        except Exception as exc:
            logger.warning("FashionCLIP subcategory failed: %s", exc)
            tags["subcategory"] = None
            confidence["subcategory"] = 0.0
            needs_review["subcategory"] = True
            failures.append("subcategory")
    else:
        tags["subcategory"] = None
        confidence["subcategory"] = 1.0
        needs_review["subcategory"] = False

    # ── Embellishments (multi-label binary checks) ──
    try:
        matched_embellishments: list[str] = []
        for emb in EMBELLISHMENTS:
            phrase = EMBELLISHMENT_DISPLAY[emb]
            pos = EMBELLISHMENT_POSITIVE_TEMPLATE.format(phrase=phrase)
            neg = EMBELLISHMENT_NEGATIVE_TEMPLATE.format(phrase=phrase)
            present, score = zero_shot_binary_check(
                image_url, pos, neg, threshold=EMBELLISHMENT_THRESHOLD,
            )
            if present:
                matched_embellishments.append(emb)
        tags["embellishments"] = json.dumps(matched_embellishments)
        confidence["embellishments"] = 1.0
        needs_review["embellishments"] = False
        logger.info("FashionCLIP embellishments: %s", matched_embellishments)
    except Exception as exc:
        logger.warning("FashionCLIP embellishments failed: %s", exc)
        tags["embellishments"] = json.dumps([])
        confidence["embellishments"] = 0.0
        needs_review["embellishments"] = True
        failures.append("embellishments")

    # ── Garment length (single-best zero-shot) ──
    try:
        gl_label, gl_conf = zero_shot_classify(image_url, GARMENT_LENGTHS)
        confidence["garment_length"] = gl_conf
        if gl_conf < CONFIDENCE_THRESHOLD:
            tags["garment_length"] = None
            needs_review["garment_length"] = True
        else:
            tags["garment_length"] = gl_label
            needs_review["garment_length"] = False
        logger.info(
            "FashionCLIP garment_length: %s (%.2f) needs_review=%s",
            gl_label, gl_conf, needs_review["garment_length"],
        )
    except Exception as exc:
        logger.warning("FashionCLIP garment_length failed: %s", exc)
        tags["garment_length"] = None
        confidence["garment_length"] = 0.0
        needs_review["garment_length"] = True
        failures.append("garment_length")

    # Denim colour refinement: denim is inherently blue/navy, never black.
    if tags.get("fabric_type") == "denim" and tags.get("dominant_color") == "black":
        tags["dominant_color"] = "navy"
        confidence["dominant_color"] = min(confidence.get("dominant_color", 0.0) + 0.03, 1.0)
        needs_review["dominant_color"] = False
        logger.info("Denim colour refinement: black -> navy")

    # Color sanity: if the model says the item is "white" but the
    # centre of the photo is dark, flag it for review.  This catches
    # the common case where a dark garment on a light background fools
    # the model into seeing the background as the dominant colour.
    if tags.get("dominant_color") == "white" and confidence.get("dominant_color", 1.0) < 0.35:
        from app.style_embeddings import _center_luminance
        try:
            lum = _center_luminance(image_url)
            if lum < 100:  # centre is significantly darker than white
                needs_review["dominant_color"] = True
                logger.info("Color sanity: white prediction over dark centre (lum=%.1f) -> review", lum)
        except Exception:
            pass

    # Dedicated gender classification with ambiguity handling.
    try:
        from app.style_embeddings import get_embedding
        image_emb = get_embedding(image_url)
        gender_label, gender_conf = classify_target_gender(image_emb)
        confidence["target_gender"] = gender_conf
        if gender_conf < CONFIDENCE_THRESHOLD:
            tags["target_gender"] = None
            needs_review["target_gender"] = True
        else:
            tags["target_gender"] = gender_label
            needs_review["target_gender"] = False
        logger.info(
            "FashionCLIP target_gender: %s (%.2f) needs_review=%s",
            gender_label, gender_conf, needs_review["target_gender"],
        )
    except Exception as exc:
        logger.warning("FashionCLIP target_gender failed: %s", exc)
        tags["target_gender"] = None
        confidence["target_gender"] = 0.0
        needs_review["target_gender"] = True
        failures.append("target_gender")

    # Multi-label style-tag classification (belted, wrap_style, etc.)
    try:
        from app.style_embeddings import zero_shot_classify_multi

        matched_tags = zero_shot_classify_multi(image_url, STYLE_TAG_CANDIDATES)
        tags["style_tags"] = matched_tags
        confidence["style_tags"] = 1.0
        needs_review["style_tags"] = False
        logger.info("FashionCLIP style_tags: %s", matched_tags)
    except Exception as exc:
        logger.warning("FashionCLIP style_tags failed: %s", exc)
        tags["style_tags"] = []
        confidence["style_tags"] = 0.0
        needs_review["style_tags"] = True

    # Derive formality_score from occasion_tag (deterministic, always confident).
    occasion = tags.get("occasion_tag")
    if occasion:
        formality_score = FORMALITY_MAP.get(occasion, 3)
        if occasion not in FORMALITY_MAP:
            logger.info("FALLBACK: occasion=%r not in FORMALITY_MAP, using formality=3", occasion)
    else:
        formality_score = 3
        logger.info("FALLBACK: occasion_tag is None, using formality=3")
    tags["formality_score"] = formality_score
    confidence["formality_score"] = 1.0
    needs_review["formality_score"] = False

    result = {**tags, "_confidence": confidence, "_needs_review": needs_review}

    if failures:
        result["_warnings"] = f"Failed fields: {', '.join(failures)}"

    logger.info(
        "FINAL _tag_item_fashion_clip(%s) tags=%s conf=%s",
        image_url,
        {k: v for k, v in tags.items() if not k.startswith("_")},
        {k: round(v, 4) for k, v in confidence.items()},
    )
    return result


def _tag_item(image_url: str) -> dict:
    if TAGGING_PROVIDER == "fashion_clip":
        return _tag_item_fashion_clip(image_url)
    return _tag_item_vision_api(image_url)


@router.post("/tag-item")
def tag_item(body: TagItemRequest):
    return _tag_item(body.image_url)
