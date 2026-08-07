from pydantic import BaseModel


class AdminInputLogfile(BaseModel):
    file: str
