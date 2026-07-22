"""One-time migration: create try_on_usage table for rate limiting.

Safe to re-run (CREATE TABLE IF NOT EXISTS).

Usage:
    cd server && python scripts/migrate_tryon_usage.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "stylemate.db"


def migrate() -> None:
    if not DB_PATH.exists():
        print(f"No database found at {DB_PATH} — skipping (tables will be created on next startup).")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS try_on_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            usage_date DATE NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, usage_date)
        )
        """
    )
    print("  Table 'try_on_usage' created (or already exists).")

    # Index for fast lookups by user_id + usage_date
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_try_on_usage_user_date ON try_on_usage (user_id, usage_date)"
    )
    print("  Index 'ix_try_on_usage_user_date' created (or already exists).")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
