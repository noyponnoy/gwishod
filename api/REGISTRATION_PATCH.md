# GW protocol — API registration patch

Apply these edits to `api/src/endpoints/server.py` to register the GW routers.

## 1. Add imports (next to the existing awg imports, around line 31-33)

```python
from src.endpoints.v3.gw import bot_api as gw_bot_api
from src.endpoints.v3.gw import client as gw_client_api
```

## 2. Register routers (next to the existing awg include_router calls, around line 179-181)

```python
app.include_router(gw_bot_api.router)
app.include_router(gw_client_api.router)
```

## 3. Add `coincurve` to `api/requirements.txt`

```
coincurve>=20.0.0
```

(`cryptography` is already present and provides AES-256-GCM.)

---

## Notes

- The client endpoint `/vpn/api/v1/user/server_gw` is automatically protected by the
  existing `AndroidSignatureMiddleware` (EXPECTED_SECRET), because it matches the
  `/vpn/api/v1/user/*` POST pattern. No extra auth wiring needed.

- The bot endpoints `/vpn/api/v1/bot/servers_gw/*` are unprotected, matching the
  convention of every other `/bot/*` route in this repo. The bot itself gates access
  via the `@admin_only` decorator on its handlers.
