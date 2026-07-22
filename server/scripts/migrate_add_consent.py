import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "stylemate.db"


def migrate():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = {row[1] for row in cursor.fetchall()}

    new_columns = {
        "photo_consent": "INTEGER DEFAULT 0",
        "consent_given_at": "DATETIME",
        "consent_version": "VARCHAR",
        "photo_url": "VARCHAR",
    }

    for col_name, col_def in new_columns.items():
        if col_name not in columns:
            print(f"Adding column: {col_name}")
            conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
