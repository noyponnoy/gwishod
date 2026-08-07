from pydantic import BaseModel
from typing import Any


class ResponseJsonMessage(BaseModel):
    status_code: int
    info: str

    def to_dict(self):
        return self.model_dump()


class ResponseJson(BaseModel):
    success: bool
    message: ResponseJsonMessage
    data: Any = {}

    def to_dict(self):
        return self.model_dump()
