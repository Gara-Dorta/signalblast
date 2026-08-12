import asyncio

from signalblast.admin import Admin
from signalblast.storage import SignalblastStorage, UserTable


def make_storage() -> SignalblastStorage:
    return SignalblastStorage(":memory:")


def test_user_table_add_remove_contains() -> None:
    storage = make_storage()
    table = UserTable(storage, "subscribers")

    assert "uuid-1" not in table

    asyncio.run(table.add("uuid-1", "+1234"))
    assert "uuid-1" in table
    assert table.get_phone_number("uuid-1") == "+1234"
    assert len(table) == 1

    asyncio.run(table.remove("uuid-1"))
    assert "uuid-1" not in table
    assert len(table) == 0


def test_user_table_iteration_is_ordered() -> None:
    storage = make_storage()
    table = UserTable(storage, "subscribers")

    for uuid in ("uuid-a", "uuid-b", "uuid-c"):
        asyncio.run(table.add(uuid, None))

    assert list(table) == ["uuid-a", "uuid-b", "uuid-c"]


def test_subscribers_and_banned_users_are_independent_tables() -> None:
    storage = make_storage()
    subscribers = UserTable(storage, "subscribers")
    banned_users = UserTable(storage, "banned_users")

    asyncio.run(subscribers.add("uuid-1", "+1234"))
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
