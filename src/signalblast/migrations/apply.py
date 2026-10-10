"""Creates and upgrades signalblast's database schema, tracked with sqlite's `user_version`.

Each `vN` module is a schema version, which never changes once it is released. A database at version N
has had the first N applied, and the missing ones are applied in order in a single transaction.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from signalblast.migrations import v1, v2

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS = (v1, v2)

SCHEMA_VERSION = len(MIGRATIONS)


def migrate(conn: sqlite3.Connection, data_dir: Path | None) -> None:
    """`data_dir` is where the files of older versions are looked for when the database is created."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == SCHEMA_VERSION:
        return
    if version > SCHEMA_VERSION:
        msg = f"The database was created by a newer signalblast (schema {version}), please upgrade signalblast"
        raise RuntimeError(msg)

    imported: list[Path] = []
    conn.execute("BEGIN")
    try:
        if version == 0:
            dev_tables = v1.rename_dev_tables(conn)
            _run_script(conn, v1.SQL)
            imported = v1.import_old_data(conn, dev_tables, data_dir)
        # A new database got v1 above
        for migration in MIGRATIONS[max(version, 1) :]:
            _run_script(conn, migration.SQL)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    except BaseException:
        conn.rollback()
        raise
    conn.commit()

    for path in imported:
        path.rename(path.with_name(path.name + ".migrated"))
        logger.info("Imported %s into the database and renamed it to %s.migrated", path.name, path.name)


def _run_script(conn: sqlite3.Connection, script: str) -> None:
    # `executescript` would commit the open transaction, run the statements one by one instead
    for statement in script.split(";"):
        if statement.strip():
            conn.execute(statement)
