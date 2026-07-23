"""FashionCLIP embedding computation for clothing items.

Uses the open-source patrickjohncyh/fashion-clip model from Hugging Face
to generate image embeddings for visual similarity matching.

Expected CPU speed: ~2-5 seconds per image without GPU.
Model download on first use: ~500MB, cached in ~/.cache/huggingface/.
"""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MODEL_ID = "patrickjohncyh/fashion-clip"
SERVER_DIR = Path(__file__).resolve().parents[1]
UPLOADS_DIR = SERVER_DIR / "uploads"

_model = None
_processor = None

# In-memory cache: item_id -> embedding list
_embedding_cache: dict[int, list[float]] = {}


@dataclass
class RankedProduct:
    product: object
    similarity_score: float | None = None


def _get_model():
    """Lazy-load FashionCLIP model and processor.

    First call downloads the model from HuggingFace (~500MB).
    Subsequent calls reuse the cached instance.
    """
    global _model, _processor
    if _model is not None:
        return _model, _processor

    import torch
    from transformers import CLIPModel, CLIPProcessor

    logger.info("Loading FashionCLIP model: %s (first run downloads ~500MB)", MODEL_ID)
    _processor = CLIPProcessor.from_pretrained(MODEL_ID)
    _model = CLIPModel.from_pretrained(MODEL_ID)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    _model = _model.to(device).eval()
    logger.info("FashionCLIP loaded on %s", device)

    return _model, _processor


def _resolve_image(image_path_or_url: str) -> Image.Image:
    """Load an image from a local path or URL and return a PIL Image."""
    if image_path_or_url.startswith("/"):
        local_path = Path(image_path_or_url)
        if not local_path.exists():
            local_path = SERVER_DIR / image_path_or_url.lstrip("/")
        if local_path.exists():
            return Image.open(local_path).convert("RGB")
        raise FileNotFoundError(f"Image not found: {local_path}")

    if image_path_or_url.startswith(("http://", "https://")):
        import httpx

        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(image_path_or_url)
            resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name
        return Image.open(tmp_path).convert("RGB")

    raise ValueError(f"Unsupported image path/URL: {image_path_or_url}")


def get_embedding(image_path_or_url: str) -> list[float]:
    """Compute FashionCLIP embedding for an image.

    Args:
        image_path_or_url: Local path (e.g. "/uploads/abc.jpg") or HTTP(S) URL.

    Returns:
        Normalized embedding vector as a list of floats.
    """
    import torch

    image = _resolve_image(image_path_or_url)
    model, processor = _get_model()

    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        features = model.get_image_features(**inputs)

    if not isinstance(features, torch.Tensor):
        features = features.pooler_output
    features = features / features.norm(dim=-1, keepdim=True)
    return features.squeeze().cpu().numpy().tolist()


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors.

    Returns:
        Similarity score in [-1, 1]. 1.0 = identical, 0.0 = orthogonal.
    """
    a = np.asarray(vec_a, dtype=np.float64)
    b = np.asarray(vec_b, dtype=np.float64)

    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


LABEL_TEMPLATES = [
    "a photo of a {label}",
    "a person wearing a {label}",
    "a clothing item that is {label}",
    "a close-up product photo of a {label}",
]

CONFIDENCE_THRESHOLD: float = 0.24
GENDER_MARGIN: float = 0.05


def _center_luminance(image_path_or_url: str) -> float:
    """Compute average luminance of the centre region of an image.

    Returns a value in [0, 255].  Used as a sanity check: if the model
    says an item is "white" but the centre of the photo is dark, the
    prediction is likely picking up on the background.
    """
    image = _resolve_image(image_path_or_url)
    w, h = image.size
    cx, cy = w // 2, h // 2
    box = (cx - w // 6, cy - h // 6, cx + w // 6, cy + h // 6)
    crop = image.crop(box).convert("L")  # greyscale
    pixels = list(crop.getdata())
    return sum(pixels) / len(pixels) if pixels else 128.0

_ensembled_label_cache: dict[str, list[float]] = {}


def get_ensembled_label_embedding(label: str) -> list[float]:
    """Compute an averaged text embedding for *label* across prompt templates.

    Encodes each formatted template through FashionCLIP, averages the
    resulting embeddings, and returns the L2-normalized result.
    Results are cached per label since they never change.
    """
    if label in _ensembled_label_cache:
        return _ensembled_label_cache[label]

    import torch

    model, processor = _get_model()
    texts = [t.format(label=label) for t in LABEL_TEMPLATES]
    inputs = processor(text=texts, return_tensors="pt", padding=True, truncation=True)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        embs = model.get_text_features(**inputs)
    if not isinstance(embs, torch.Tensor):
        embs = embs.pooler_output

    avg = embs.mean(dim=0)
    avg = avg / avg.norm(dim=-1, keepdim=True)
    result = avg.cpu().numpy().tolist()
    _ensembled_label_cache[label] = result
    return result


def zero_shot_classify(
    image_path_or_url: str,
    candidate_labels: list[str],
) -> tuple[str, float]:
    """Zero-shot image classification using FashionCLIP.

    Compares the image embedding against ensembled text embeddings of
    candidate labels (each label is encoded via prompt templates and
    averaged), returning the best match and its confidence score.

    Args:
        image_path_or_url: Local path (e.g. "/uploads/abc.jpg") or HTTP(S) URL.
        candidate_labels: List of text labels to classify against.

    Returns:
        (best_label, confidence) where confidence is cosine similarity in [-1, 1].
    """
    import torch

    image_emb = get_embedding(image_path_or_url)
    image_vec = torch.tensor(image_emb, dtype=torch.float32)

    sims = []
    for label in candidate_labels:
        text_vec = torch.tensor(
            get_ensembled_label_embedding(label), dtype=torch.float32
        )
        sims.append(float(torch.dot(image_vec, text_vec).item()))

    best_idx = int(np.argmax(sims))
    return candidate_labels[best_idx], sims[best_idx]


STYLE_TAG_THRESHOLD: float = 0.12


def zero_shot_classify_multi(
    image_path_or_url: str,
    candidate_labels: list[str],
    threshold: float = STYLE_TAG_THRESHOLD,
) -> list[str]:
    """Multi-label zero-shot classification using FashionCLIP.

    Unlike ``zero_shot_classify`` which returns only the single best label,
    this function returns **all** labels whose cosine similarity exceeds
    ``threshold``.  Useful for style-tag detection where a garment can
    have multiple attributes (e.g. both ``belted`` and ``structured``).

    Args:
        image_path_or_url: Local path or HTTP(S) URL to the image.
        candidate_labels: Style-tag labels to evaluate.
        threshold: Minimum similarity to keep a label (default 0.12).

    Returns:
        List of matching labels (may be empty).
    """
    import torch

    image_emb = get_embedding(image_path_or_url)
    image_vec = torch.tensor(image_emb, dtype=torch.float32)

    matches: list[str] = []
    for label in candidate_labels:
        text_vec = torch.tensor(
            get_ensembled_label_embedding(label), dtype=torch.float32
        )
        sim = float(torch.dot(image_vec, text_vec).item())
        if sim >= threshold:
            matches.append(label)

    return matches


GENDER_PHRASES = [
    "a piece of men's clothing",
    "a piece of women's clothing",
    "a unisex clothing item that suits anyone",
]

_gender_phrase_cache: dict[str, list[float]] = {}


def classify_target_gender(
    image_embedding: list[float],
) -> tuple[str, float]:
    """Dedicated gender classification with ambiguity handling.

    Uses specific gendered phrases rather than generic labels.  If the top
    two scores are within ``GENDER_MARGIN`` of each other the result
    defaults to "unisex" since ambiguous items genuinely are unisex-wearable.

    Args:
        image_embedding: Pre-computed image embedding (list of floats).

    Returns:
        (gender_label, confidence).  ``gender_label`` is one of
        "men", "women", or "unisex".
    """
    import torch

    # Encode the 3 phrases if not cached.
    uncached = [p for p in GENDER_PHRASES if p not in _gender_phrase_cache]
    if uncached:
        model, processor = _get_model()
        inputs = processor(
            text=uncached, return_tensors="pt", padding=True, truncation=True,
        )
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        with torch.no_grad():
            embs = model.get_text_features(**inputs)
        if not isinstance(embs, torch.Tensor):
            embs = embs.pooler_output
        embs = embs / embs.norm(dim=-1, keepdim=True)
        for phrase, emb in zip(uncached, embs.cpu().numpy().tolist()):
            _gender_phrase_cache[phrase] = emb

    image_vec = torch.tensor(image_embedding, dtype=torch.float32)

    scored: list[tuple[str, float]] = []
    for phrase in GENDER_PHRASES:
        text_vec = torch.tensor(_gender_phrase_cache[phrase], dtype=torch.float32)
        scored.append((phrase, float(torch.dot(image_vec, text_vec).item())))

    scored.sort(key=lambda x: x[1], reverse=True)

    best_phrase, best_score = scored[0]
    second_phrase, second_score = scored[1]

    if best_score - second_score < GENDER_MARGIN:
        return "unisex", best_score

    label_map = {
        "a piece of men's clothing": "men",
        "a piece of women's clothing": "women",
        "a unisex clothing item that suits anyone": "unisex",
    }
    return label_map[best_phrase], best_score


def compute_and_store_embedding(item_id: int, db: Session) -> None:
    """Compute FashionCLIP embedding for a clothing item and persist to DB.

    Skips if the item already has an embedding stored or cached.
    Opens its own DB session for thread safety.
    """
    if item_id in _embedding_cache:
        return

    from app.models import ClothingItem

    item = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not item or not item.image_url:
        return

    if item.embedding_json:
        try:
            _embedding_cache[item_id] = json.loads(item.embedding_json)
            return
        except (json.JSONDecodeError, TypeError):
            pass

    try:
        embedding = get_embedding(item.image_url)
    except Exception:
        logger.exception("Failed to compute embedding for item %d", item_id)
        return

    _embedding_cache[item_id] = embedding
    item.embedding_json = json.dumps(embedding)
    db.commit()
    logger.info("Stored embedding for item %d", item_id)


def compute_missing_embeddings(db: Session) -> int:
    """Compute embeddings for all items that don't have one yet.

    Returns the number of items processed.
    """
    from app.models import ClothingItem

    items = (
        db.query(ClothingItem)
        .filter(ClothingItem.embedding_json.is_(None))
        .all()
    )

    for item in items:
        if item.id in _embedding_cache:
            continue
        compute_and_store_embedding(item.id, db)

    return len(items)


def rank_by_visual_fit(
    item_id: int, products: list, db: Session
) -> list[RankedProduct]:
    """Rank products by visual similarity to the given item's embedding.

    Falls back to returning products with ``similarity_score=None`` when
    the reference item has no stored embedding or the model is unavailable.
    """
    ref_embedding = _embedding_cache.get(item_id)
    if ref_embedding is None:
        from app.models import ClothingItem

        item = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
        if item and item.embedding_json:
            try:
                ref_embedding = json.loads(item.embedding_json)
                _embedding_cache[item_id] = ref_embedding
            except (json.JSONDecodeError, TypeError):
                pass

    scored: list[RankedProduct] = []
    for p in products:
        if ref_embedding and p.image_url:
            try:
                prod_emb = get_embedding(p.image_url)
                score = cosine_similarity(ref_embedding, prod_emb)
            except Exception:
                score = None
        else:
            score = None
        scored.append(RankedProduct(product=p, similarity_score=score))

    scored.sort(key=lambda r: r.similarity_score or 0.0, reverse=True)
    return scored
