"""One-time migration: add body_type to users and style_tags to clothing_items.

Safe to re-run (silently skips columns that already exist).

Usage:
    cd server && python scripts/migrate_body_type_rules.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "stylemate.db"

USER_COLUMNS = [
    "body_type TEXT",
]

CLOTHING_COLUMNS = [
    "style_tags TEXT",
]


def migrate() -> None:
    if not DB_PATH.exists():
        print(f"No database found at {DB_PATH} — skipping (tables will be created on next startup).")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # ── users table ──
    cur.execute("PRAGMA table_info(users)")
    existing_users = {row[1] for row in cur.fetchall()}

    for col_def in USER_COLUMNS:
        col_name = col_def.split()[0]
        if col_name in existing_users:
            print(f"  users.{col_name} already exists — skipping.")
        else:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col_def}")
            print(f"  Added users.{col_name}.")

    # ── clothing_items table ──
    cur.execute("PRAGMA table_info(clothing_items)")
    existing_clothing = {row[1] for row in cur.fetchall()}

    for col_def in CLOTHING_COLUMNS:
        col_name = col_def.split()[0]
        if col_name in existing_clothing:
            print(f"  clothing_items.{col_name} already exists — skipping.")
        else:
            cur.execute(f"ALTER TABLE clothing_items ADD COLUMN {col_def}")
            print(f"  Added clothing_items.{col_name}.")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
