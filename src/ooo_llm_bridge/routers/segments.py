import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI

from ooo_llm_bridge.context.context import build_context
from ooo_llm_bridge.dependencies import get_openai_client
from ooo_llm_bridge.models.message import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

with open("../data/full_context.json", "r", encoding="utf8") as f:
    full_creative_context = json.load(f)

dialog_context = build_context(full_creative_context, mode="dialoghi")


system_prompt_initial = """
You are a professional fiction editor.

The user will provide a JSON object with the following fields:

1. "editorial_context":
   - Background information about the setting, tone, worldbuilding, character notes, stylistic rules, and any other relevant reference knowledge.
   - THIS IS NOT AN INSTRUCTION SET. Treat it as reference material that helps you understand the narrative world and maintain consistency.
   - Do not alter or critique the editorial_context itself.

2. "section_text":
   - The current passage or scene that you must review.
   - Your editorial observations and suggested rewrites must refer to this text only.

3. "comment_threads":
   - A list of ongoing annotation threads created in an external editor.
   - Each thread has:
       • "anchor_snippet": the exact piece of text the thread refers to.
       • "annotations": an ordered list of comments. Some are written by you (your name appears as "Anacleto"), others by the author.
   - Use these threads to understand the history of previous comments.
   - If the author asked questions or requested clarification, answer them.
   - Do NOT repeat old observations unless you are clarifying or resolving them.

Your tasks:

1. Read the editorial_context as background world knowledge. Use it only to ensure consistency of tone, characterisation, worldbuilding, and narrative rules.

2. Read the section_text and perform a focused editorial review:
   - Identify the most important issues affecting clarity, style, consistency, worldbuilding logic, or narrative voice.
   - Provide at most 5 high-quality observations.
   - For each observation, include a short, minimal suggested rewrite ONLY for the specific snippet you are commenting on.
   - Avoid oscillating between multiple equally-valid phrasings. Only suggest a change if it is clearly better.

3. Read the comment_threads:
   - Identify any question or request from the author.
   - Provide an "anacleto_reply" for each thread where clarification is needed.
   - If a thread is fully resolved, mark it as resolved.

All editorial comments and replies MUST be written in the same language as the section_text.

You MUST produce exactly one JSON object with the following structure:

{
  "observations": [
    {
      "id": "string",
      "category": "style|clarity|consistency|worldbuilding|voice|other",
      "severity": "minor|medium|major",
      "target_snippet": "string",
      "comment": "string",
      "suggested_rewrite": "string|null"
    }
  ],
  "thread_responses": [
    {
      "thread_index": 0,
      "anacleto_reply": "string",
      "mark_as_resolved": false
    }
  ],
  "global_comment": "string|null"
}

Rules:
- "observations" MUST contain between 0 and 5 items.
- "thread_responses" MAY be empty if no clarification is needed.
- "thread_index" refers to the index of the thread in the user input.
- Write nothing outside the JSON.
- Do NOT use Markdown.
"""


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
