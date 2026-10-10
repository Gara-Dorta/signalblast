"""signalblast's database schema, one module per version, see `apply.py`."""

from signalblast.migrations.apply import SCHEMA_VERSION, migrate

__all__ = ["SCHEMA_VERSION", "migrate"]
