from pydantic import BaseModel, Field


class Config(BaseModel):
    domain: str
    link: str
    name: str
    protocol: str
    security: str
    transport: str
    connection_type: str = Field(alias="type")

    model_config = {"populate_by_name": True}
