#!/usr/bin/env python3
"""Delete all VFS rows and re-run init_db seed (AGENTS.md, skills, memory dirs)."""

from __future__ import annotations

import sys
from pathlib import Path

# server/ as import root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.config import settings
from app.database import init_db


def main() -> None:
    with psycopg.connect(settings.DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM vfs_files")
            deleted = cur.rowcount
            cur.execute("SELECT COUNT(*) FROM vfs_files")
            remaining = cur.fetchone()[0]

    print(f"Deleted vfs_files rows: {deleted}")
    print(f"Remaining vfs_files rows: {remaining}")

    init_db()

    with psycopg.connect(settings.DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT path, is_dir FROM vfs_files ORDER BY path")
            rows = cur.fetchall()

    print(f"\nSeeded {len(rows)} VFS entries:")
    for path, is_dir in rows:
        kind = "dir" if is_dir else "file"
        print(f"  [{kind}] {path}")


if __name__ == "__main__":
    main()
