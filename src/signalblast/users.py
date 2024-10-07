from __future__ import annotations

import csv
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class Users:
    _uuid_str = "uuid"
    _phone_number_str = "phone_number"

    def __init__(self, save_path: Path) -> None:
        self.save_path = save_path
        self.data: dict[str, str | None] = {}

    async def add(self, uuid: str, phone_number: str | None) -> None:
        self.data[uuid] = phone_number
        await self.save_to_file()

    async def remove(self, uuid: str) -> None:
        del self.data[uuid]
        await self.save_to_file()

    async def save_to_file(self) -> None:
        with self.save_path.open("w") as f:
            csv_writer = csv.DictWriter(f, fieldnames=[self._uuid_str, self._phone_number_str])
            csv_writer.writeheader()
            for uuid, phone_number in self.data.items():
                csv_writer.writerow({self._uuid_str: uuid, self._phone_number_str: phone_number})

    @staticmethod
    async def _load_from_file(save_path: Path) -> Users:
        users = Users(save_path)
        with save_path.open() as f:
            csv_reader = csv.DictReader(f)
            for line in csv_reader:
                users.data[line[Users._uuid_str]] = line[Users._phone_number_str]
        return users

    def get_phone_number(self, uuid: str) -> str | None:
        return self.data.get(uuid)

    def __iter__(self) -> Iterator[str | None]:
        yield from self.data

    def __contains__(self, uuid: str) -> bool:
        return uuid in self.data

    def __len__(self) -> int:
        return len(self.data)

    @staticmethod
    async def load_from_file(save_path: Path) -> Users:
        if not save_path.exists():
            return Users(save_path)

        return await Users._load_from_file(save_path)
