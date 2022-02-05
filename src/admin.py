import bcrypt
import os
from typing import Optional


class Admin():
    save_path = './data/admin.txt'

    @classmethod
    async def create(cls, admin_password: Optional[str]) -> None:
        self = Admin()
        self.admin_id = None
        await self.set_hashed_password(admin_password)
        return self

    def get_hashed_password(self):
        return self._hashed_password

    async def set_hashed_password(self, password: str):
        if password is None:
            self._hashed_password = ''.encode()
        else:
            self._hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        await self.save_to_file()

    async def add(self, id: str, admin_password: str) -> bool:
        if bcrypt.checkpw(admin_password.encode(), self.get_hashed_password()):
            self.admin_id = id
            await self.save_to_file()
            return True
        else:
            return False

    async def remove(self, admin_password: str) -> bool:
        if bcrypt.checkpw(admin_password.encode(), self.get_hashed_password()):
            self.admin_id = None
            await self.save_to_file()
            return True
        else:
            return False

    async def save_to_file(self) -> None:
        with open(self.save_path, "w") as f:
            f.write(self.admin_id + '\n')
            f.write(self.get_hashed_password().decode())

    @staticmethod
    async def _load_from_file():
        admin = Admin()
        with open(Admin.save_path, "r") as f:
            admin.admin_id = f.readline().rstrip()
            admin._hashed_password = f.readline().encode()
        return admin

    @staticmethod
    async def load_from_file(admin_password: Optional[str]):
        if not os.path.exists(Admin.save_path):
            return await Admin.create(admin_password)

        admin = await Admin._load_from_file()
        # If no password was given assume we want to keep the one from the file
        if admin_password is not None:
            await admin.set_hashed_password(admin_password)
        return admin
