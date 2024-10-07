import bcrypt

from signalblast.utils import get_code_data_path


class Admin:
    save_path = get_code_data_path() / "admin.txt"

    def __init__(self) -> None:
        self.admin_id: str = None
        self._hashed_password: str = None

    @classmethod
    async def create(cls, admin_password: str | None) -> None:
        self = Admin()
        self.admin_id = None
        await self.set_hashed_password(admin_password)
        return self

    def get_hashed_password(self) -> str:
        return self._hashed_password

    async def set_hashed_password(self, password: str) -> None:
        if password is None:
            self._hashed_password = b""
        else:
            self._hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        await self.save_to_file()

    async def add(self, admin_id: str, admin_password: str | None) -> bool:
        if admin_password is None:
            return False

        if bcrypt.checkpw(admin_password.encode(), self.get_hashed_password()):
            self.admin_id = admin_id
            await self.save_to_file()
            return True
        return False

    async def remove(self, admin_password: str | None) -> bool:
        if admin_password is None:
            return False

        if bcrypt.checkpw(admin_password.encode(), self.get_hashed_password()):
            self.admin_id = None
            await self.save_to_file()
            return True
        return False

    async def save_to_file(self) -> None:
        with self.save_path.open("w") as f:
            if self.admin_id is None:
                f.write("\n")
            else:
                f.write(self.admin_id + "\n")
            f.write(self.get_hashed_password().decode())

    @staticmethod
    async def _load_from_file() -> "Admin":
        admin = Admin()
        with Admin.save_path.open() as f:
            admin.admin_id = f.readline().rstrip()
            admin._hashed_password = f.readline().encode()  # noqa: SLF001

        if admin.admin_id == "":
            admin.admin_id = None

        return admin

    @staticmethod
    async def load_from_file(admin_password: str | None) -> "Admin":
        if not Admin.save_path.exists():
            return await Admin.create(admin_password)

        admin = await Admin._load_from_file()
        # Overwrite the password in the file, if no password was given assume we want to keep the one from the file
        if admin_password is not None:
            await admin.set_hashed_password(admin_password)
        return admin
