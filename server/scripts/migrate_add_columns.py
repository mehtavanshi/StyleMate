"""One-time migration: add fabric_type, fit_type, sleeve_length,
formality_score columns to clothing_items table.

Safe to re-run (silently skips columns that already exist).

Usage:
    cd server && python scripts/migrate_add_columns.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "stylemate.db"

COLUMNS = [
    "fabric_type TEXT",
    "fit_type TEXT",
    "sleeve_length TEXT",
    "formality_score INTEGER",
]


def migrate() -> None:
    if not DB_PATH.exists():
        print(f"No database found at {DB_PATH} — skipping (tables will be created on next startup).")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Get existing columns
    cur.execute("PRAGMA table_info(clothing_items)")
    existing = {row[1] for row in cur.fetchall()}

    for col_def in COLUMNS:
        col_name = col_def.split()[0]
        if col_name in existing:
            print(f"  Column '{col_name}' already exists — skipping.")
        else:
            cur.execute(f"ALTER TABLE clothing_items ADD COLUMN {col_def}")
            print(f"  Added column '{col_name}'.")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
