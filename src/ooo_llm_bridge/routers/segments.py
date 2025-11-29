import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI

from ooo_llm_bridge.context.context import build_context
from ooo_llm_bridge.dependencies import get_openai_client
from ooo_llm_bridge.models.message import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

with open("data/full_context.json", "r", encoding="utf8") as f:
    full_creative_context = json.load(f)

dialog_context = build_context(full_creative_context, mode="dialoghi")

with open("data/prompts/system.txt", "r", encoding="utf8") as f:
    system_prompt_initial = f.read()


user_prompt_template_first = """
CONTEXT FOR THE EDITOR:
The following information may include background notes, stylistic constraints, worldbuilding details, tone guidelines, or other relevant instructions. Use this only as contextual knowledge.

{context}

TEXT TO REVIEW:
{text}
"""


ask_router = APIRouter()


@ask_router.post(path="/ask")
async def ask(
    chat_request: ChatRequest,
    response_model=ChatResponse,
    client: OpenAI = Depends(get_openai_client),
):
    mode = chat_request.mode or "dialoghi"
    comment_threads = chat_request.comment_threads

    logger.info(
        f"Received request for section uuid={chat_request.uuid} and mode={mode}"
    )
    logger.debug(f"Received comment_threads={comment_threads}")
    logger.info(chat_request.text)

    user_payload = {
        "editorial_context": dialog_context,
        "section_text": chat_request.text,
        "comment_threads": [c.model_dump_json() for c in chat_request.comment_threads],
    }

    try:
        completion = client.chat.completions.create(
            model=chat_request.model,
            messages=[
                {"role": "system", "content": system_prompt_initial},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        reply = completion.choices[0].message.content
        logger.info(reply)

        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, details=str(e)) from e
