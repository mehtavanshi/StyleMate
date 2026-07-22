#!/usr/bin/env python3
"""
Standalone test for FreeSelfHostedProvider.

Uploads two fixture images to local storage, calls the provider directly,
and saves the output image locally.  Run from the server/ directory:

    FREE_PROVIDER_SPACE_ID=<your-space> python -m scripts.test_free_provider
"""

import asyncio
import os
import sys
from pathlib import Path

# ── Bootstrap paths ──
SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from dotenv import load_dotenv

load_dotenv(SERVER_DIR / ".env")

from app.storage import get_storage_provider
from app.try_on_service import FreeSelfHostedProvider, ProviderUnavailableError

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
PERSON_IMAGE = FIXTURES_DIR / "person.jpg"
GARMENT_IMAGE = FIXTURES_DIR / "garment.jpg"
OUTPUT_PATH = Path(__file__).resolve().parent / "output_free_provider.png"


async def main() -> None:
    if not PERSON_IMAGE.exists():
        sys.exit(f"Missing fixture: {PERSON_IMAGE}")
    if not GARMENT_IMAGE.exists():
        sys.exit(f"Missing fixture: {GARMENT_IMAGE}")

    space_id = os.getenv("FREE_PROVIDER_SPACE_ID", "")
    if not space_id:
        sys.exit(
            "Set FREE_PROVIDER_SPACE_ID env var before running.\n"
            "  FREE_PROVIDER_SPACE_ID=your-username/your-space python -m scripts.test_free_provider"
        )

    print(f"Space ID  : {space_id}")
    print(f"Person    : {PERSON_IMAGE}")
    print(f"Garment   : {GARMENT_IMAGE}")

    provider = get_storage_provider()

    # Upload fixtures to local storage so render() can read_file() them
    person_bytes = PERSON_IMAGE.read_bytes()
    garment_bytes = GARMENT_IMAGE.read_bytes()

    person_key = provider.save_file(person_bytes, "test_person.jpg", "image/jpeg")
    garment_key = provider.save_file(garment_bytes, "test_garment.jpg", "image/jpeg")
    print(f"Uploaded  : person_key={person_key}  garment_key={garment_key}")

    # Call the provider
    hf_provider = FreeSelfHostedProvider()
    try:
        result = await hf_provider.render(
            user_photo_url=person_key,
            garment_image_url=garment_key,
            category="upper_body",
        )
    except ProviderUnavailableError as exc:
        sys.exit(f"Provider unavailable: {exc}")
    except Exception as exc:
        sys.exit(f"Provider error: {type(exc).__name__}: {exc}")

    print(f"Result key: {result.result_storage_key}")
    print(f"Model used: {result.model_used}")

    # Save the result image locally
    result_bytes = provider.read_file(result.result_storage_key)
    OUTPUT_PATH.write_bytes(result_bytes)
    print(f"Output saved to: {OUTPUT_PATH}")
    print("SUCCESS")


if __name__ == "__main__":
    asyncio.run(main())
