import os
import pickle
from typing import Optional


class Admin():
    save_path = './data/admin.pickle'

    def __init__(self, admin_pass: Optional[str]) -> None:
        self.admin_id = None
        self._admin_pass = admin_pass

    async def add(self, id: str, admin_pass: str) -> bool:
        if self._admin_pass == admin_pass:
            self.admin_id = id
            await self.save_admin()
            return True
        else:
            return False

    async def remove(self, admin_pass: str) -> bool:
        if self._admin_pass == admin_pass:
            self.admin_id = None
            await self.save_admin()
            return True
        else:
            return False

    async def save_admin(self):
        with open(self.save_path, 'wb') as f:
            pickle.dump(self, f)

    @staticmethod
    def load_admin(admin_pass: Optional[str]):
        if not os.path.exists(Admin.save_path):
            return Admin(admin_pass)

        with open(Admin.save_path, 'rb') as f:
            admin = pickle.load(f)
            assert isinstance(admin, Admin)
            if admin_pass is not None:
                admin._admin_pass = admin_pass
            return admin
