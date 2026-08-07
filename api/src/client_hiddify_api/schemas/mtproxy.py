from pydantic import BaseModel


class Mtproxy(BaseModel):
    link: str
    title: str
