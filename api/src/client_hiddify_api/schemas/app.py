from typing import List

from pydantic import BaseModel

from .app_install import AppInstall


class App(BaseModel):
    deeplink: str
    description: str
    guide_url: str
    icon_url: str
    install: List[AppInstall]
    title: str
