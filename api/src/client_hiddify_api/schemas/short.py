from pydantic import BaseModel


class Short(BaseModel):
    expire_in: int
    full_url: str
    short: str
