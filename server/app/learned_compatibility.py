"""Optional learned outfit-compatibility scoring via outfit-transformer.

Wraps the third-party outfit-transformer project (bigohofone/outfit-transformer)
which is pretrained on the Polyvore outfit-compatibility dataset.

Setup required:
  1. Git clone into server/third_party/outfit-transformer/
  2. Download checkpoint: ./scripts/download_checkpoint.sh
  3. Set USE_LEARNED_COMPATIBILITY=true in .env

Expected CPU speed: ~1-3s per pair (model + CLIP image encoding).
Checkpoint size: ~500MB.
"""

from __future__ import annotations

import glob
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SERVER_DIR = Path(__file__).resolve().parents[2]
OUTFIT_TRANSFORMER_DIR = SERVER_DIR / "third_party" / "outfit-transformer"
CHECKPOINT_DIR = OUTFIT_TRANSFORMER_DIR / "checkpoints"

_model = None


def _load_outfit_transformer():
    """Lazy-load the outfit-transformer model.

    Adds the third-party repo to sys.path so its ``src`` package resolves,
    then loads the CLIP variant from the first ``.pt`` checkpoint found.
    """
    global _model
    if _model is not None:
        return _model

    repo_str = str(OUTFIT_TRANSFORMER_DIR)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)

    pt_files = sorted(glob.glob(str(CHECKPOINT_DIR / "*.pt")))
    if not pt_files:
        raise FileNotFoundError(
            f"No checkpoint found in {CHECKPOINT_DIR}. "
            "Run ./scripts/download_checkpoint.sh to download the pretrained weights."
        )

    checkpoint_path = pt_files[0]
    logger.info("Loading outfit-transformer from %s", checkpoint_path)

    from src.models.load import load_model

    _model = load_model(model_type="clip", checkpoint=checkpoint_path)
    _model.eval()
    logger.info("Outfit-transformer loaded (device=%s)", _model.device)
    return _model


def get_learned_compatibility(item_image_urls: list[str]) -> float | None:
    """Score outfit compatibility using the learned outfit-transformer.

    Args:
        item_image_urls: List of image paths/URLs (e.g. ["/uploads/a.jpg", "/uploads/b.jpg"]).

    Returns:
        Compatibility score in [0, 1], or None if the model is unavailable.
    """
    try:
        model = _load_outfit_transformer()
    except Exception:
        logger.exception("Outfit-transformer unavailable")
        return None

    try:
        from app.style_embeddings import _resolve_image

        from src.data.datatypes import FashionCompatibilityQuery, FashionItem

        items = []
        for url in item_image_urls:
            pil_img = _resolve_image(url)
            items.append(FashionItem(image=pil_img))

        query = FashionCompatibilityQuery(outfit=items)

        import torch

        with torch.no_grad():
            score_tensor = model.predict_score(
                query=[query],
                use_precomputed_embedding=False,
            )

        return float(score_tensor.squeeze().item())

    except Exception:
        logger.exception("Learned compatibility scoring failed")
        return None
