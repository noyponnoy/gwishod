from fastapi import FastAPI
from fastapi.routing import APIRoute

from src.endpoints.v1 import ads, login, packages, servers, traffic, signup_otp, subscription, bot_api, connections
from src.endpoints.v1.auth_middleware import AndroidSignatureMiddleware
from src.endpoints.v1.admin import add_server as v1_admin_add_server
from src.endpoints.v1.payment import get_pay_url, web_hook
from src.endpoints.v1.support import get_user_history, update_invoice, update_user

from src.endpoints.v2 import tariff as v2_tariff
from src.endpoints.v2.admin import tariff as v2_admin_tariff

from src.endpoints.v3.danger.user import user as danger_user
from src.endpoints.v3.danger.user import traffic as danger_traffic

from src.endpoints.v3.client import user as client_user
from src.endpoints.v3.client import servers as client_servers
from src.endpoints.v3.client import tariff as client_tariff
from src.endpoints.v3.client import code as client_code
from src.endpoints.v3.client import client_transfer

from src.endpoints.v3.admin import user as admin_user
from src.endpoints.v3.admin import info as admin_info
from src.endpoints.v3.admin import update as admin_update

from src.endpoints.v3.a3xui import user as a3xui_user
from src.endpoints.v3.a3xui import server as a3xui_server
from src.endpoints.v3.a3xui.admin import admin as a3xui_admin
from src.endpoints.v3.a3xui.admin import upload_file as a3xui_upload_file

from src.endpoints.v3.awg import bot_api as awg_bot_api
from src.endpoints.v3.awg import client as awg_client_api
from src.endpoints.v3.awg import agent_api as awg_agent_api

app = FastAPI()

# ─────────────────────────────────────────────
#  Middleware: проверка подписи Android-клиента
# ─────────────────────────────────────────────

app.add_middleware(AndroidSignatureMiddleware)

# ─────────────────────────────────────────────
#  Old API v1 and v2
# ─────────────────────────────────────────────

app.add_api_route("/vpn/api/v1/user/ads", ads.ads, methods=["POST"])
app.add_api_route("/vpn/api/v1/user/signup", signup_otp.signup, methods=["POST"])
app.add_api_route("/vpn/api/v1/user/otp", signup_otp.otp_verify, methods=["POST"])
app.add_api_route("/vpn/api/v1/user/loginAnonymousUser", login.login_anonymous_user, methods=["POST"])
app.add_api_route("/vpn/api/v1/user/profile", login.profile, methods=["POST"])
app.add_api_route("/vpn/api/v1/user/packages", packages.get_packages, methods=["POST"])
app.add_api_route("/vpn/api/v1/user/server", servers.get_servers, methods=["POST"])
app.add_api_route("/vpn/api/v1/user/updateTotalUploadDownload", traffic.update_total_upload_download, methods=["POST"])
app.add_api_route("/vpn/api/v1/user/subscription", subscription.update_subscription, methods=["POST"])
app.add_api_route("/vpn/api/v1/admin/addServer", v1_admin_add_server.add_server, methods=["POST"])
app.add_api_route("/vpn/api/v1/getpayurl", get_pay_url.get_pay_url, methods=["GET", "POST"])
app.add_api_route("/vpn/client/payment/webhook", web_hook.web_hook, methods=["POST"])

# ─────────────────────────────────────────────
#  Connections tracking
# ─────────────────────────────────────────────

app.add_api_route("/vpn/api/v1/user/connection/update", connections.update_connection, methods=["POST"])
app.add_api_route("/vpn/api/v1/user/servers/load", connections.get_servers_load, methods=["POST"])
app.add_api_route("/vpn/api/v1/bot/servers/stats", connections.get_servers_stats, methods=["GET"])

# ─────────────────────────────────────────────
#  Bot API (for Telegram admin bot)
# ─────────────────────────────────────────────

app.add_api_route("/vpn/api/v1/bot/users/all", bot_api.bot_get_all_users, methods=["GET"])
app.add_api_route("/vpn/api/v1/bot/users/search", bot_api.bot_search_user, methods=["GET"])
app.add_api_route("/vpn/api/v1/bot/users/search_by_mnemonic", bot_api.bot_search_by_mnemonic, methods=["GET"])
app.add_api_route("/vpn/api/v1/bot/users/get", bot_api.bot_get_user, methods=["GET"])
app.add_api_route("/vpn/api/v1/bot/users/premium/set", bot_api.bot_set_premium, methods=["POST"])
app.add_api_route("/vpn/api/v1/bot/users/premium/revoke", bot_api.bot_revoke_premium, methods=["POST"])
app.add_api_route("/vpn/api/v1/bot/analytics/summary", bot_api.bot_analytics_summary, methods=["GET"])
app.add_api_route("/vpn/api/v1/bot/servers/all", bot_api.bot_get_all_servers, methods=["GET"])
app.add_api_route("/vpn/api/v1/bot/servers/get", bot_api.bot_get_server, methods=["GET"])
app.add_api_route("/vpn/api/v1/bot/servers/create", bot_api.bot_create_server, methods=["POST"])
app.add_api_route("/vpn/api/v1/bot/servers/update", bot_api.bot_update_server, methods=["POST"])
app.add_api_route("/vpn/api/v1/bot/servers/delete", bot_api.bot_delete_server, methods=["POST"])
app.add_api_route("/vpn/api/v1/bot/servers/toggle", bot_api.bot_toggle_server, methods=["POST"])
app.add_api_route("/vpn/api/v1/bot/servers_vless/all", bot_api.bot_get_all_servers_vless, methods=["GET"])
app.add_api_route("/vpn/api/v1/bot/servers_vless/get", bot_api.bot_get_server_vless, methods=["GET"])
app.add_api_route("/vpn/api/v1/bot/servers_vless/create", bot_api.bot_create_server_vless, methods=["POST"])
app.add_api_route("/vpn/api/v1/bot/servers_vless/update", bot_api.bot_update_server_vless, methods=["POST"])
app.add_api_route("/vpn/api/v1/bot/servers_vless/delete", bot_api.bot_delete_server_vless, methods=["POST"])
app.add_api_route("/vpn/api/v1/bot/tariffs/all", bot_api.bot_get_all_tariffs, methods=["GET"])
app.add_api_route("/vpn/api/v1/bot/tariffs/get", bot_api.bot_get_tariff, methods=["GET"])
app.add_api_route("/vpn/api/v1/bot/tariffs/create", bot_api.bot_create_tariff, methods=["POST"])
app.add_api_route("/vpn/api/v1/bot/tariffs/update", bot_api.bot_update_tariff, methods=["POST"])
app.add_api_route("/vpn/api/v1/bot/tariffs/delete", bot_api.bot_delete_tariff, methods=["POST"])
app.add_api_route("/vpn/api/v1/bot/invoices/all", bot_api.bot_get_all_invoices, methods=["GET"])

# ─────────────────────────────────────────────
#  API v3
# ─────────────────────────────────────────────

# /vpn/api/v3/danger/user/...
app.add_api_route("/vpn/api/v3/danger/user/insert", danger_user.insert, methods=["POST"])
app.add_api_route("/vpn/api/v3/danger/user/update", danger_user.update, methods=["POST"])
app.add_api_route("/vpn/api/v3/danger/user/delete", danger_user.delete, methods=["POST"])
app.add_api_route("/vpn/api/v3/danger/user/find", danger_user.find, methods=["POST"])
app.add_api_route("/vpn/api/v3/danger/user/findall", danger_user.find_all, methods=["GET"])

# /vpn/api/v3/danger/user/traffic/...
app.add_api_route("/vpn/api/v3/danger/user/traffic/insert", danger_traffic.insert, methods=["POST"])
app.add_api_route("/vpn/api/v3/danger/user/traffic/find", danger_traffic.find, methods=["GET"])
app.add_api_route("/vpn/api/v3/danger/user/traffic/findall", danger_traffic.find_all, methods=["GET"])

# /vpn/api/v3/client/user/...
app.add_api_route("/vpn/api/v3/client/user/create", client_user.create, methods=["POST"])
app.add_api_route("/vpn/api/v3/client/user/get", client_user.get, methods=["GET"])
app.add_api_route("/vpn/api/v3/client/user/updatetraffic", client_user.update_traffic, methods=["PUT"])
app.add_api_route("/vpn/api/v3/client/user/login", client_user.login, methods=["GET"])
app.add_api_route("/vpn/api/v3/client/user/activatecode", client_user.activate_code, methods=["PUT"])

# /vpn/api/v3/client/servers/...
app.add_api_route("/vpn/api/v3/client/servers/get", client_servers.get_servers, methods=["GET"])

# /vpn/api/v3/client/tariff/...
app.add_api_route("/vpn/api/v3/client/tariff/get", client_tariff.get_tariff, methods=["GET"])

# /vpn/api/v3/client/payments/...
app.add_api_route("/vpn/api/v3/client/payments/getpayurl", get_pay_url.get_pay_url, methods=["POST"])

# /vpn/api/v3/client/code/...
app.add_api_route("/vpn/api/v3/client/code/getall", client_code.get_all_user_codes, methods=["GET"])
app.add_api_route("/vpn/api/v3/client/code/get", client_code.get_code, methods=["GET"])

# transfer user from v1 to v3
app.add_api_route("/vpn/api/v3/client/transfer", client_transfer.transfer, methods=["PUT"])

# /vpn/api/v3/admin/user/...
app.add_api_route("/vpn/api/v3/admin/user/create", admin_user.create, methods=["POST"])
app.add_api_route("/vpn/api/v3/admin/user/login", admin_user.login, methods=["PUT"])
app.add_api_route("/vpn/api/v3/admin/user/update", admin_user.update, methods=["PUT"])
app.add_api_route("/vpn/api/v3/admin/user/delete", admin_user.delete, methods=["DELETE"])
app.add_api_route("/vpn/api/v3/admin/user/token/expired/update", admin_user.update_token, methods=["PUT"])

# /vpn/api/v3/admin/info/...
app.add_api_route("/vpn/api/v3/admin/info/getpremiumusers", admin_info.get_premium_users, methods=["GET"])
app.add_api_route("/vpn/api/v3/admin/info/getnotpremiumusers", admin_info.get_not_premium_users, methods=["GET"])
app.add_api_route("/vpn/api/v3/admin/info/getallusers", admin_info.get_all_users, methods=["GET"])
app.add_api_route("/vpn/api/v3/admin/info/getuser", admin_info.get_user_by_id, methods=["GET"])
app.add_api_route("/vpn/api/v3/admin/info/getusercodes", admin_info.get_user_codes, methods=["GET"])
app.add_api_route("/vpn/api/v3/admin/info/getusertraffic", admin_info.get_user_traffic, methods=["GET"])
app.add_api_route("/vpn/api/v3/admin/info/gettarrifs", admin_info.get_tarriffs, methods=["GET"])
app.add_api_route("/vpn/api/v3/admin/info/getservers", admin_info.get_servers, methods=["GET"])

# /vpn/api/v3/admin/update/...
app.add_api_route("/vpn/api/v3/admin/update/user", admin_update.update_user, methods=["PUT"])

# /vpn/api/v3/3xui/user/...
app.add_api_route("/vpn/api/v3/3xui/user/login", a3xui_user.create_or_login, methods=["POST"])
app.add_api_route("/vpn/api/v3/3xui/user/free", a3xui_user.set_free, methods=["POST"])
app.add_api_route("/vpn/api/v3/3xui/user/payhand", a3xui_user.update_payment_hand, methods=["GET"])
app.add_api_route("/vpn/api/v3/3xui/user/exps", a3xui_user.get_user_exps, methods=["GET"])
app.add_api_route("/vpn/sub/GW-VPN/{tg_id}", a3xui_user.get_user_subscription, methods=["GET"])
app.add_api_route("/vpn/sub/GW-VPN/{tg_id}/", a3xui_user.get_user_subscription, methods=["GET"])
app.add_api_route("/vpn/sub/GW-VPN/{tg_id}/{subsname}", a3xui_user.get_user_subscription_sname, methods=["GET"])
app.add_api_route("/vpn/api/v3/3xui/user/getdates", a3xui_user.get_dates, methods=["GET"])

# /vpn/api/v3/3xui/server/...
app.add_api_route("/vpn/api/v3/3xui/server/servers", a3xui_server.get_servers, methods=["GET"])
app.add_api_route("/vpn/api/v3/3xui/server/server", a3xui_server.get_server, methods=["GET"])
app.add_api_route("/vpn/api/v3/3xui/server/server", a3xui_server.update_server, methods=["PUT"])
app.add_api_route("/vpn/api/v3/3xui/server/server", a3xui_server.delete_server, methods=["DELETE"])
app.add_api_route("/vpn/api/v3/3xui/server/server", a3xui_server.add_server, methods=["POST"])

# /vpn/api/v3/3xui/admin/...
app.add_api_route("/vpn/api/v3/3xui/admin/massnotif", a3xui_admin.massnotif, methods=["GET"])
app.add_api_route("/vpn/api/v3/3xui/admin/statistics", a3xui_admin.statistics, methods=["GET"])
app.add_api_route("/vpn/api/v3/3xui/admin/upload", a3xui_upload_file.upload_file, methods=["POST"])

# AWG Bot APIs
app.include_router(awg_bot_api.router)
app.include_router(awg_client_api.router)
app.include_router(awg_agent_api.router)
