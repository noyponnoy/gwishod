from pydantic import BaseModel


class PongOutput(BaseModel):
    msg: str
