from typing import Optional
from pydantic import BaseModel


class TryOnCapabilities(BaseModel):
    configured: bool
    model: str


class TryOnJobOut(BaseModel):
    provider: str
    job_id: str
    status: str
    result_url: Optional[str] = None
    error: Optional[str] = None
