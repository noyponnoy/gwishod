from pydantic import BaseModel, Field


class AppInstall(BaseModel):
    title: str
    install_type: str = Field(alias="type")
    url: str

    model_config = {"populate_by_name": True}
