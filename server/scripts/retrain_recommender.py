#!/usr/bin/env python3
"""Train the LightFM outfit recommender from accumulated OutfitFeedback.

Usage:
    cd server && python scripts/retrain_recommender.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, SessionLocal, engine  # noqa: E402

Base.metadata.create_all(bind=engine)

from app.recommender import train_model  # noqa: E402


def main():
    db = SessionLocal()
    try:
        stats = train_model(db)
    finally:
        db.close()

    print("Recommender training complete:")
    print(f"  model_path : {stats['model_path']}")
    print(f"  backend    : {stats['backend']}")
    print(f"  users      : {stats['n_users']}")
    print(f"  combos     : {stats['n_combos']}")
    print(f"  features   : {stats['n_features']}")


if __name__ == "__main__":
    main()
