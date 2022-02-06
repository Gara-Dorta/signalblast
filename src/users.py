import os
import pickle


class Users():
    def __init__(self, save_path: str) -> None:
        self.save_path = save_path
        self.data = set()

    async def add(self, element: str) -> None:
        self.data.add(element)
        await self.save_to_file()

    async def remove(self, element: str) -> None:
        self.data.remove(element)
        await self.save_to_file()

    async def save_to_file(self):
        with open(self.save_path, "w") as f:
            for i, subscriber in enumerate(self.data):
                if i < len(self.data):
                    f.write(subscriber + '\n')
                else:
                    f.write(subscriber)

    @staticmethod
    async def _load_from_file(save_path):
        users = Users(save_path)
        with open(save_path, "r") as f:
            users.data.add(f.readline().rstrip())
        return users

    def __iter__(self):
        for user in self.data:
            yield user

    def __contains__(self, user: str):
        return user in self.data

    def __len__(self):
        return len(self.data)

    @staticmethod
    async def load_from_file(save_path):
        if not os.path.exists(save_path):
            return Users(save_path)

        return await Users._load_from_file(save_path)
