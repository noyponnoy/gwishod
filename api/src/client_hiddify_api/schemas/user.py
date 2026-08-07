from typing import Optional

from pydantic import BaseModel


class User(BaseModel):
    added_by_uuid: Optional[str] = None
    comment: Optional[str] = None
    current_usage_GB: int
    ed25519_private_key: Optional[str] = None
    ed25519_public_key: Optional[str] = None
    enable: bool
    id: Optional[int] = None
    is_active: bool
    lang: str
    last_online: Optional[str] = None
    last_reset_time: Optional[str] = None
    mode: str
    name: str
    package_days: int
    start_date: Optional[str] = None
    telegram_id: int
    usage_limit_GB: int
    uuid: Optional[str] = None
    wg_pk: Optional[str] = None
    wg_psk: Optional[str] = None
    wg_pub: Optional[str] = None

    @classmethod
    def new(
        cls,
        current_usage_GB: int = 0,
        enable: bool = True,
        is_active: bool = True,
        lang: str = "",
        mode: str = "",
        name: str = "",
        package_days: int = 0,
        telegram_id: int = 0,
        usage_limit_GB: int = 0,
        **kwargs,
    ) -> "User":
        return cls(
            current_usage_GB=current_usage_GB,
            enable=enable,
            is_active=is_active,
            lang=lang,
            mode=mode,
            name=name,
            package_days=package_days,
            telegram_id=telegram_id,
            usage_limit_GB=usage_limit_GB,
            **kwargs,
        )
