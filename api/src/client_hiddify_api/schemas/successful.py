from pydantic import BaseModel


class Successful(BaseModel):
    msg: str
    status: int
