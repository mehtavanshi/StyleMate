#!/usr/bin/env python3
"""CLI wrapper around compute_missing_embeddings().

Usage:
    python -m server.scripts.backfill_embeddings
    python -m server.scripts.backfill_embeddings --batch-size 10 --delay 2
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.style_embeddings import compute_missing_embeddings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill FashionCLIP embeddings for items missing them.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Items per batch (default: 5)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between batches (default: 1.0)",
    )
    args = parser.parse_args()

    result = compute_missing_embeddings(
        db=None,
        batch_size=args.batch_size,
        delay=args.delay,
    )

    total = result["total"]
    succeeded = result["succeeded"]
    failures = result["failures"]

    print(f"\n{'=' * 50}")
    print("Backfill complete.")
    print(f"  Total processed : {total}")
    print(f"  Succeeded       : {succeeded}")
    print(f"  Failed          : {len(failures)}")

    if failures:
        reasons = Counter(r for _, r in failures)
        print("\n  Failures by reason:")
        for reason, count in reasons.most_common():
            print(f"    - {reason}: {count}")
            ids = [str(fid) for fid, r in failures if r == reason]
            print(f"      Item IDs: {', '.join(ids)}")


if __name__ == "__main__":
    main()
