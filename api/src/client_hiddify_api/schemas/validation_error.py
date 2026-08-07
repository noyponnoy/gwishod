from typing import Dict, List, Optional

from pydantic import BaseModel


class ValidationError(BaseModel):
    detail: Dict[str, Dict[str, List[Optional[str]]]]
    message: str
