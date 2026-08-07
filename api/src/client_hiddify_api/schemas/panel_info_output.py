from pydantic import BaseModel


class PanelInfoOutput(BaseModel):
    version: str
