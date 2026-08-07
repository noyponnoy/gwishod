from typing import Any

from pydantic import BaseModel


class HttpError(BaseModel):
    detail: Any
    message: str
