from __future__ import annotations

import csv
import os


class Users:
    _uuid_str = "uuid"
    _phone_number_str = "phone_number"

    def __init__(self, save_path: str) -> None:
        self.save_path = save_path
        self.data: dict[str, str | None] = {}

    async def add(self, uuid: str, phone_number: str | None) -> None:
        self.data[uuid] = phone_number
        await self.save_to_file()

    async def remove(self, uuid: str) -> None:
        del self.data[uuid]
        await self.save_to_file()

    async def save_to_file(self):
        with open(self.save_path, "w") as f:
            csv_writer = csv.DictWriter(f, fieldnames=[self._uuid_str, self._phone_number_str])
            csv_writer.writeheader()
            for uuid, phone_number in self.data.items():
                csv_writer.writerow({self._uuid_str: uuid, self._phone_number_str: phone_number})

    @staticmethod
    async def _load_from_file(save_path) -> Users:
        users = Users(save_path)
        with open(save_path) as f:
            csv_reader = csv.DictReader(f)
            for line in csv_reader:
                users.data[line[Users._uuid_str]] = line[Users._phone_number_str]
        return users

    def get_phone_number(self, uuid: str) -> str | None:
        return self.data.get(uuid)

    def __iter__(self):
        for uuid in self.data:
            yield uuid

    def __contains__(self, uuid: str):
        return uuid in self.data

    def __len__(self):
        return len(self.data)

    @staticmethod
    async def load_from_file(save_path) -> Users:
        if not os.path.exists(save_path):
            return Users(save_path)

        return await Users._load_from_file(save_path)
