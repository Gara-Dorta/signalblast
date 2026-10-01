"""bcrypt is slow on purpose, so hashing and checking run in a thread to keep the event loop responsive."""

from __future__ import annotations

import asyncio

import bcrypt


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())


async def check_password(password: str, password_hash: bytes) -> bool:
    try:
        return await asyncio.to_thread(bcrypt.checkpw, password.encode(), password_hash)
    except ValueError:  # Not a valid bcrypt hash
        return False
