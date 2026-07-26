#!/usr/bin/env python3
"""Create the item_pair_scores table.

Engine-agnostic, unlike the older migrate_*.py scripts in here which open
stylemate.db directly with sqlite3 and therefore never touch the configured
Postgres database.

    python scripts/migrate_pair_cache.py          # create
    python scripts/migrate_pair_cache.py --drop   # drop (forces a full rescore)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect

from app.database import engine
from app.models import ItemPairScore


def main(drop: bool) -> None:
    table = ItemPairScore.__table__
    print(f"engine: {str(engine.url).split('@')[-1]}")

    if drop:
        table.drop(bind=engine, checkfirst=True)
        print("dropped item_pair_scores")
        return

    if inspect(engine).has_table(table.name):
        print("item_pair_scores already exists, nothing to do")
        return
    table.create(bind=engine)
    print("created item_pair_scores")


if __name__ == "__main__":
    main("--drop" in sys.argv)
