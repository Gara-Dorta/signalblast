import os
import pickle
from typing import Set


class Subscribers(Set[str]):
    save_path = './data/subscribers.pickle'

    async def add(self, element: str) -> None:
        new_subscribers = super().add(element)
        await self.save_subscribers()

    async def remove(self, element: str) -> None:
        new_subscribers = super().remove(element)
        await self.save_subscribers()

    async def save_subscribers(self):
        with open(self.save_path, 'wb') as f:
            pickle.dump(self, f)

    @staticmethod
    def load_subscribers():
        if not os.path.exists(Subscribers.save_path):
            return Subscribers()

        with open(Subscribers.save_path, 'rb') as f:
            subscribers = pickle.load(f)
            assert isinstance(subscribers, Subscribers)
            return subscribers
