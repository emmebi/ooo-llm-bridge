from pydantic import BaseModel


class ChatRequest(BaseModel):
    text: str
    model: str


class ChatResponse(BaseModel):
    reply: str
