from typing import Optional

from pydantic import BaseModel


class PostUser(BaseModel):
    added_by_uuid: Optional[str] = None
    comment: Optional[str] = None
    current_usage_GB: int
    ed25519_private_key: str
    ed25519_public_key: str
    enable: bool
    is_active: bool
    lang: str
    last_online: Optional[str] = None
    last_reset_time: Optional[str] = None
    mode: str
    name: str
    package_days: int
    start_date: str
    telegram_id: int
    usage_limit_GB: int
    uuid: Optional[str] = None
    wg_pk: str
    wg_psk: str
    wg_pub: str
