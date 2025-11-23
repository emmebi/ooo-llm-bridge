from typing import Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    text: str
    model: str
    uuid: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
