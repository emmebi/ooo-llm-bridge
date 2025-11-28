from typing import Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class ChatRequest(BaseModel):
    text: str
    model: str
    comment_threads: list[CommentThread]
    uuid: Optional[str] = None
    mode: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str

class CommentThread(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    anchor_snippet: str
    annotations: list[Annotation]

class Annotation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    author: str
    datetime: datetime
    content: str
