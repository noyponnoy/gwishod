from pydantic import BaseModel


class Profile(BaseModel):
    admin_message_html: str
    admin_message_url: str
    brand_icon_url: str
    brand_title: str
    doh: str
    lang: str
    profile_remaining_days: int
    profile_reset_days: int
    profile_title: str
    profile_url: str
    profile_usage_current: int
    profile_usage_total: int
    speedtest_enable: bool
    telegram_bot_url: str
    telegram_id: int
    telegram_proxy_enable: bool
