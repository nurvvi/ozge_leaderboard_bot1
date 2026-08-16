from __future__ import annotations

import argparse
import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.migrations import reset_production_data


def backup_database(source_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    destination = backup_dir / f"{source_path.stem}.pre_reset_{stamp}.db"
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up and reset ÖZGEcoins production data while preserving users")
    parser.add_argument("--db", type=Path, default=Path("activity_bot.db"))
    parser.add_argument("--backup-dir", type=Path, default=Path("backups"))
    parser.add_argument("--confirm", required=True, help="Must be exactly RESET")
    args = parser.parse_args()
    if args.confirm != "RESET":
        raise SystemExit("Refusing reset: pass --confirm RESET")
    backup = backup_database(args.db, args.backup_dir)
    asyncio.run(reset_production_data(args.db))
    print(f"Backup: {backup}")
    print("Reset complete; Telegram users were preserved.")


if __name__ == "__main__":
    main()
