from typing import final

from pydantic import BaseModel


@final
class UserAccount(BaseModel):
    username: str
    hashed_password: str
    display_name: str


FAKE_USER = UserAccount(
    username="yanghangethan@gmail.com",
    hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # 明文是 secret
    display_name="yh",
)
