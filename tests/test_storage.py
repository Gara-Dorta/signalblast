import asyncio

import pytest
from signalbot import StorageError

from signalblast.admin import Admin
from signalblast.storage import SignalblastStorage, UserTable
from signalblast.utils import TimestampData


def make_storage() -> SignalblastStorage:
    return SignalblastStorage(":memory:")


def test_user_table_add_remove_contains() -> None:
    storage = make_storage()
    table = UserTable(storage, "subscribers")

    assert "uuid-1" not in table

    asyncio.run(table.add("uuid-1"))
    assert "uuid-1" in table
    assert len(table) == 1

    asyncio.run(table.remove("uuid-1"))
    assert "uuid-1" not in table
    assert len(table) == 0


def test_user_table_iteration_is_ordered() -> None:
    storage = make_storage()
    table = UserTable(storage, "subscribers")

    for uuid in ("uuid-a", "uuid-b", "uuid-c"):
        asyncio.run(table.add(uuid))

    assert list(table) == ["uuid-a", "uuid-b", "uuid-c"]


def test_subscribers_and_banned_users_are_independent_tables() -> None:
    storage = make_storage()
    subscribers = UserTable(storage, "subscribers")
    banned_users = UserTable(storage, "banned_users")

    asyncio.run(subscribers.add("uuid-1"))
    assert "uuid-1" in subscribers
    assert "uuid-1" not in banned_users


def test_admin_table_roundtrip() -> None:
    storage = make_storage()
    assert storage.get_admin() is None

    storage.set_admin("admin-uuid", b"hashed")
    assert storage.get_admin() == ("admin-uuid", b"hashed")

    storage.set_admin(None, b"other-hash")
    assert storage.get_admin() == (None, b"other-hash")


def test_ping_roundtrip() -> None:
    storage = make_storage()
    assert storage.get_ping() is None

    storage.set_ping("group-1", 60)
    assert storage.get_ping() == ("group-1", 60)

    storage.clear_ping()
    assert storage.get_ping() is None


def test_last_broadcast_roundtrip() -> None:
    storage = make_storage()
    assert storage.get_last_broadcast_uuid() is None

    storage.set_last_broadcast_uuid("uuid-1")
    assert storage.get_last_broadcast_uuid() == "uuid-1"

    storage.set_last_broadcast_uuid("uuid-2")
    assert storage.get_last_broadcast_uuid() == "uuid-2"


def test_admin_load_creates_when_missing() -> None:
    storage = make_storage()

    admin = asyncio.run(Admin.load(storage, "secret"))

    assert admin.admin_id is None
    assert storage.get_admin() is not None


def test_admin_add_and_remove_with_password() -> None:
    storage = make_storage()
    admin = asyncio.run(Admin.load(storage, "secret"))

    assert asyncio.run(admin.add("uuid-1", "wrong")) is False
    assert admin.admin_id is None

    assert asyncio.run(admin.add("uuid-1", "secret")) is True
    assert admin.admin_id == "uuid-1"

    assert asyncio.run(admin.remove("wrong")) is False
    assert admin.admin_id == "uuid-1"

    assert asyncio.run(admin.remove("secret")) is True
    assert admin.admin_id is None


def test_admin_persists_across_load_calls() -> None:
    storage = make_storage()
    admin = asyncio.run(Admin.load(storage, "secret"))
    asyncio.run(admin.add("uuid-1", "secret"))

    reloaded = asyncio.run(Admin.load(storage, None))

    assert reloaded.admin_id == "uuid-1"


def test_broadcast_timestamps_save_read_delete() -> None:
    storage = make_storage()
    data = TimestampData(author="uuid-1", timestamp=1000, broadcast_timestamps={"uuid-1": 1000, "uuid-2": 1001})

    storage.save_broadcast_timestamps(data)
    assert storage.read_broadcast_timestamps("uuid-1", 1000) == data

    with pytest.raises(StorageError):
        storage.read_broadcast_timestamps("uuid-1", 999)

    assert storage.delete_broadcast_timestamps_before(1000) == 0
    assert storage.delete_broadcast_timestamps_before(1001) == 1
    with pytest.raises(StorageError):
        storage.read_broadcast_timestamps("uuid-1", 1000)


def test_signalbot_table_is_dropped() -> None:
    storage = make_storage()
    tables = {row[0] for row in storage._sqlite.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}  # noqa: SLF001
    assert "broadcast_timestamps" in tables
    assert "signalbot" not in tables
