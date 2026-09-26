import argparse
import os
from pathlib import Path
import sqlite3
import sys

from app.core.config import get_settings


def backup_database(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_file():
        raise ValueError("The source database does not exist.")
    if destination.exists():
        raise ValueError("The destination already exists; use a new path.")
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
            with sqlite3.connect(destination) as backup:
                original.backup(backup)
                if backup.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise ValueError("Database integrity verification failed.")
    except (sqlite3.Error, OSError, ValueError):
        destination.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Back up or restore SQLite into a NEW file, without replacing any existing database."
    )
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source or get_settings().sqlite_database_path
    try:
        backup_database(source, args.output)
    except (sqlite3.Error, OSError, ValueError) as exc:
        print(f"Backup was not completed ({type(exc).__name__}). Check source and destination paths.", file=sys.stderr)
        return 1
    print(f"Verified database copy written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
