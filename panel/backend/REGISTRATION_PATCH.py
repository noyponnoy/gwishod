"""GW panel registration patch (backend).

Edit panel/backend/proxy.py:

In the `JSON_BODY_PATHS` set (where AWG create/delete are already listed), add the
GW create/delete paths so POST bodies are sent as JSON instead of form-encoded:

    JSON_BODY_PATHS = {
        "/vpn/api/v1/bot/servers_awg/create",
        "/vpn/api/v1/bot/servers_awg/delete",
        "/vpn/api/v1/bot/servers_gw/create",      # <-- NEW
        "/vpn/api/v1/bot/servers_gw/delete",      # <-- NEW
    }

No other backend changes are needed — the proxy is transparent for GET/update and
the rest of the GW bot endpoints. (The /user/server_gw client endpoint is called by
the Android app directly, not the panel, so the proxy doesn't need it.)
"""
