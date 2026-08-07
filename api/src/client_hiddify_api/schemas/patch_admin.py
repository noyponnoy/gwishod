from typing import Optional

from pydantic import BaseModel


class PatchAdmin(BaseModel):
    can_add_admin: bool
    comment: str
    lang: str
    max_active_users: int
    max_users: int
    mode: str
    name: str
    parent_admin_uuid: Optional[str] = None
    telegram_id: int
    uuid: Optional[str] = None
