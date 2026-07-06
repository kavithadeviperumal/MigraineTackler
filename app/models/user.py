import hashlib
import os
from datetime import datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    username: str = Field(unique=True, index=True)
    password_hash: str

    @staticmethod
    def hash_password(password: str) -> str:
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        return salt.hex() + ":" + key.hex()

    @staticmethod
    def verify_password(password: str, stored: str) -> bool:
        try:
            salt_hex, key_hex = stored.split(":")
            key = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000)
            return key.hex() == key_hex
        except Exception:
            return False
