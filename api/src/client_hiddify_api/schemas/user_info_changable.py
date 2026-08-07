from pydantic import BaseModel


class UserInfoChangable(BaseModel):
    language: str
    telegram_id: int
