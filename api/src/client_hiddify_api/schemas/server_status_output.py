from typing import Dict

from pydantic import BaseModel


class ServerStatusOutput(BaseModel):
    stats: Dict[str, str]
    usage_history: Dict[str, str]
