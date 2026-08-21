"""GW protocol server pojo — MongoDB document model for a GW node.

A GW server describes one VPS node running the GW installer (see vps/install.sh):
  * the SSH endpoint (where the SSH-over-payload tunnel terminates)
  * the HTTP/WS proxy endpoint (the CDN-fronted "Upgrade: websocket" front)
  * the SSH credentials + payload the Android client uses to build the tunnel
  * status / premium / country metadata for the server list UI

Modeled on api/src/db/v3/awg/server_pojo.py — the closest standalone-tunnel analog.
"""
import time
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient

# NOTE: matches the hard-coded connection pattern used by every other pojo in this repo.
MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "servers_gw"

_client: Optional[AsyncIOMotorClient] = None


def _db():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGODB_URI)
    return _client[DB_NAME]


class ServerPojo:
    """One GW server node. `ip_address` (the SSH host) is the natural primary key,
    but we also keep a stable `id` for the client-facing list."""

    def __init__(
        self,
        id: str = "",
        name: str = "",                 # human label, e.g. "DE-Frankfurt-01"
        ip_address: str = "",           # SSH host (primary key)
        ssh_port: int = 22,
        ssh_username: str = "gw",
        ssh_password: str = "",
        # HTTP / WS proxy (the CDN-fronted front the client connects to)
        proxy_host: str = "",
        proxy_port: int = 80,
        proxy_scheme: str = "http",     # http | https (https => TLS to CDN)
        # HTTP-Injector payload template. Tokens the client expands:
        #   [host] [port] [protocol] [ua] [crlf] [cr] [lf] [crlf*2] [method] [ssh] [host_port]
        payload: str = "",
        sni: str = "",                  # TLS SNI (for Cloudflare fronting / direct TLS mode)
        # display / classification
        country: str = "0",
        country_code: str = "0",
        state: str = "0",               # city / region
        premium: bool = False,
        recommend: bool = False,
        priority: int = 0,
        status: bool = True,            # enabled / disabled
        # server-side host key pinning (ed25519 pub key, base64) — optional
        ssh_hostkey: str = "",
        created_at: int = int(time.time() * 1000),
        updated_at: int = int(time.time() * 1000),
    ) -> None:
        self.id = id or ip_address
        self.name = name
        self.ip_address = ip_address
        self.ssh_port = ssh_port
        self.ssh_username = ssh_username
        self.ssh_password = ssh_password
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.proxy_scheme = proxy_scheme
        self.payload = payload
        self.sni = sni
        self.country = country
        self.country_code = country_code
        self.state = state
        self.premium = premium
        self.recommend = recommend
        self.priority = priority
        self.status = status
        self.ssh_hostkey = ssh_hostkey
        self.created_at = created_at
        self.updated_at = updated_at

    # ---- serialization -------------------------------------------------------
    def to_doc(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "ip_address": self.ip_address,
            "ssh_port": self.ssh_port,
            "ssh_username": self.ssh_username,
            "ssh_password": self.ssh_password,
            "proxy_host": self.proxy_host,
            "proxy_port": self.proxy_port,
            "proxy_scheme": self.proxy_scheme,
            "payload": self.payload,
            "sni": self.sni,
            "country": self.country,
            "country_code": self.country_code,
            "state": self.state,
            "premium": self.premium,
            "recommend": self.recommend,
            "priority": self.priority,
            "status": self.status,
            "ssh_hostkey": self.ssh_hostkey,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_doc(doc: Dict[str, Any]) -> "ServerPojo":
        return ServerPojo(
            id=doc.get("id", ""),
            name=doc.get("name", ""),
            ip_address=doc.get("ip_address", ""),
            ssh_port=doc.get("ssh_port", 22),
            ssh_username=doc.get("ssh_username", "gw"),
            ssh_password=doc.get("ssh_password", ""),
            proxy_host=doc.get("proxy_host", ""),
            proxy_port=doc.get("proxy_port", 80),
            proxy_scheme=doc.get("proxy_scheme", "http"),
            payload=doc.get("payload", ""),
            sni=doc.get("sni", ""),
            country=doc.get("country", "0"),
            country_code=doc.get("country_code", "0"),
            state=doc.get("state", "0"),
            premium=doc.get("premium", False),
            recommend=doc.get("recommend", False),
            priority=doc.get("priority", 0),
            status=doc.get("status", True),
            ssh_hostkey=doc.get("ssh_hostkey", ""),
            created_at=doc.get("created_at", int(time.time() * 1000)),
            updated_at=doc.get("updated_at", int(time.time() * 1000)),
        )

    @staticmethod
    def get_collection():
        return _db()[COLLECTION_NAME]

    @staticmethod
    async def is_exist(ip_address: str) -> bool:
        doc = await ServerPojo.get_collection().find_one({"ip_address": ip_address})
        return doc is not None

    async def insert(self) -> Any:
        self.updated_at = int(time.time() * 1000)
        # upsert by ip_address
        return await ServerPojo.get_collection().update_one(
            {"ip_address": self.ip_address},
            {"$set": self.to_doc()},
            upsert=True,
        )

    async def update(self) -> Any:
        self.updated_at = int(time.time() * 1000)
        return await ServerPojo.get_collection().update_one(
            {"ip_address": self.ip_address},
            {"$set": self.to_doc()},
            upsert=True,
        )

    @staticmethod
    async def find(ip_address: str) -> Optional["ServerPojo"]:
        doc = await ServerPojo.get_collection().find_one({"ip_address": ip_address})
        return ServerPojo.from_doc(doc) if doc else None

    @staticmethod
    async def find_all() -> List["ServerPojo"]:
        cur = ServerPojo.get_collection().find().sort("priority", 1)
        return [ServerPojo.from_doc(d) async for d in cur]

    @staticmethod
    async def find_enabled() -> List["ServerPojo"]:
        cur = (
            ServerPojo.get_collection()
            .find({"status": True})
            .sort("priority", 1)
        )
        return [ServerPojo.from_doc(d) async for d in cur]

    @staticmethod
    async def delete_by_ip(ip_address: str) -> Any:
        return await ServerPojo.get_collection().delete_one({"ip_address": ip_address})
