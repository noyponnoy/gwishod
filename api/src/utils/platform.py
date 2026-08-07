"""Определение платформы клиента по bundleId (Android / iOS).

ВАЖНО: platform пишем ТОЛЬКО на login/profile, НЕ на heartbeat.
Иначе при тысячах онлайн API задыхается (это и уронило прод раньше).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

# Как в auth_middleware.ALLOWED_BUNDLE_IDS
BUNDLE_ANDROID = "app.greywebs.vpn"
BUNDLE_IOS = "com.greywebs.greywebsvpn"

PLATFORM_ANDROID = "android"
PLATFORM_IOS = "ios"
PLATFORM_UNKNOWN = "unknown"

BUNDLE_TO_PLATFORM = {
    BUNDLE_ANDROID: PLATFORM_ANDROID,
    BUNDLE_IOS: PLATFORM_IOS,
}


def bundle_id_to_platform(bundle_id: Optional[str]) -> str:
    """bundleId → android | ios | unknown."""
    if not bundle_id:
        return PLATFORM_UNKNOWN
    return BUNDLE_TO_PLATFORM.get(bundle_id.strip(), PLATFORM_UNKNOWN)


def normalize_platform(value: Optional[str]) -> str:
    v = (value or "").strip().lower()
    if v in (PLATFORM_ANDROID, PLATFORM_IOS, PLATFORM_UNKNOWN):
        return v
    return PLATFORM_UNKNOWN


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
