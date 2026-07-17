#!/usr/bin/env python3
"""One-off migration: add embedding_json column to clothing_items."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stylemate.db")


def migrate():
    print(f"Connecting to {DB_PATH} ...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE clothing_items ADD COLUMN embedding_json TEXT")
        print("  Added embedding_json to clothing_items")
    except sqlite3.OperationalError:
        print("  embedding_json already exists on clothing_items, skipping")

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    migrate()
