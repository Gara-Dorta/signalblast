from __future__ import annotations

from typing import TYPE_CHECKING

import bcrypt

if TYPE_CHECKING:
    from signalblast.storage import SignalblastStorage


class Admin:
    def __init__(self, storage: SignalblastStorage) -> None:
        self.storage = storage
        self.admin_id: str | None = None
        self._hashed_password: bytes = b""

    @classmethod
    async def create(cls, storage: SignalblastStorage, admin_password: str | None) -> Admin:
        self = Admin(storage)
        self.admin_id = None
        await self.set_hashed_password(admin_password)
        return self

    def get_hashed_password(self) -> bytes:
        return self._hashed_password

    async def set_hashed_password(self, password: str | None) -> None:
        if password is None:
            self._hashed_password = b""
        else:
            self._hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        await self.save()

    async def add(self, admin_id: str, admin_password: str | None) -> bool:
        if admin_password is None:
            return False

        if bcrypt.checkpw(admin_password.encode(), self.get_hashed_password()):
            self.admin_id = admin_id
            await self.save()
            return True
        return False

    async def remove(self, admin_password: str | None) -> bool:
        if admin_password is None:
            return False

        if bcrypt.checkpw(admin_password.encode(), self.get_hashed_password()):
            self.admin_id = None
            await self.save()
            return True
        return False

    async def save(self) -> None:
        self.storage.set_admin(self.admin_id, self.get_hashed_password())

    @staticmethod
    async def _load(storage: SignalblastStorage) -> Admin:
        admin = Admin(storage)
        row = storage.get_admin()
        if row is None:
            msg = "Admin._load called but no admin row exists in storage"
            raise RuntimeError(msg)
        admin.admin_id, admin._hashed_password = row
        return admin

    @staticmethod
    async def load(storage: SignalblastStorage, admin_password: str | None) -> Admin:
        if storage.get_admin() is None:
            return await Admin.create(storage, admin_password)

        admin = await Admin._load(storage)
        # Overwrite the password in storage, if no password was given assume we want to keep the stored one
        if admin_password is not None:
            await admin.set_hashed_password(admin_password)
        return admin
