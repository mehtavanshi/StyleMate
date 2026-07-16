#!/usr/bin/env python3
"""One-off migration: add target_gender column to users and clothing_items."""

import sqlite3
import sys
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stylemate.db")


def migrate():
    print(f"Connecting to {DB_PATH} ...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for table in ("users", "clothing_items"):
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN target_gender VARCHAR")
            print(f"  Added target_gender to {table}")
        except sqlite3.OperationalError:
            print(f"  target_gender already exists on {table}, skipping")

    cur.execute(
        "UPDATE clothing_items SET target_gender = 'unisex' WHERE target_gender IS NULL"
    )
    print(f"  Backfilled {cur.rowcount} clothing_items with default 'unisex'")

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    migrate()
