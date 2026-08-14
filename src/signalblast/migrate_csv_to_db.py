"""One-off script to migrate the pre-v2 CSV/txt data files into the sqlite database.

Usage: uv run python -m signalblast.migrate_csv_to_db

Safe to re-run: subscriber/banned-user rows are inserted with INSERT OR IGNORE, and the
admin row is upserted. The original CSV/txt files are never modified or deleted.
"""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING

from signalblast.storage import SignalblastStorage
from signalblast.utils import get_data_path

if TYPE_CHECKING:
    from pathlib import Path

_UUID_COLUMN = "uuid"


def _migrate_user_csv(storage: SignalblastStorage, csv_path: Path, table: str) -> int:
    if not csv_path.exists():
        print(f"No {csv_path.name} found, skipping.")
        return 0

    migrated = 0
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            storage.add_user(table, row[_UUID_COLUMN])
            migrated += 1

    print(f"Migrated {migrated} row(s) from {csv_path.name} into the '{table}' table.")
    return migrated


def _migrate_admin_txt(storage: SignalblastStorage, admin_txt_path: Path) -> bool:
    if not admin_txt_path.exists():
        print(f"No {admin_txt_path.name} found, skipping.")
        return False

    with admin_txt_path.open() as f:
        admin_id = f.readline().rstrip() or None
        hashed_password = f.readline().encode()

    storage.set_admin(admin_id, hashed_password)
    print(f"Migrated admin ({admin_id}) from {admin_txt_path.name}.")
    return True


def migrate() -> None:
    data_path = get_data_path()
    storage = SignalblastStorage(data_path / "signalblast.db", check_same_thread=False)

    _migrate_user_csv(storage, data_path / "subscribers.csv", "subscribers")
    _migrate_user_csv(storage, data_path / "banned_users.csv", "banned_users")
    _migrate_admin_txt(storage, data_path / "admin.txt")

    print("Migration complete. The original CSV/txt files were left untouched.")


if __name__ == "__main__":
    migrate()
