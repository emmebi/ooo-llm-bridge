from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ChatResponse(BaseModel):
    reply: str


class Annotation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    author: str
    datetime: datetime
    content: str


class CommentThread(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    thread_id: str
    anchor_snippet: str
    annotations: list[Annotation]


class ChatRequest(BaseModel):
    text: str
    model: str
    comment_threads: list[CommentThread]
    uuid: Optional[str] = None
    mode: Optional[str] = None
