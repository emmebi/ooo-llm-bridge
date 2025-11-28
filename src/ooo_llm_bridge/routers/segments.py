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

Your task is to analyze the text provided by the user and give concise, high-quality editorial feedback.

Your feedback must:
- be written in the same language as the input text
- focus on clarity, style, consistency, voice, worldbuilding integrity, and narrative flow
- be precise and non-verbose
- avoid rewriting large passages; only propose small rewrites for the specific snippet you are commenting on

VERY IMPORTANT CONSTRAINTS ABOUT THE NUMBER OF COMMENTS:
- You MUST produce at most 5 observations in total.
- If you notice many issues, choose only the 3–5 most important ones.
- Prefer issues that are major or medium severity over minor ones.
- If several issues are related or similar, merge them into a single observation instead of listing them separately.
- If you think there are additional minor issues, you may mention them briefly and in general terms ONLY in the global_comment field, without adding more observations.

You MUST return your output strictly as a JSON object following exactly this schema:

{
  "observations": [
    {
      "id": "string",                      // unique ID for the observation
      "category": "style|clarity|consistency|worldbuilding|voice|other",
      "severity": "minor|medium|major",
      "target_snippet": "string",          // short excerpt from the text that the comment refers to
      "comment": "string",                 // the editorial observation
      "suggested_rewrite": "string|null"   // optional minimal rewrite of the specific snippet
    }
  ],
  "global_comment": "string|null"
}

The length of observations MUST be between 0 and 5. Never exceed 5 elements in the observations array.

Do not add text outside the JSON.
Do not use Markdown.
Return only valid JSON.
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
    logger.debug(
        f"Received comment_threads={comment_threads}"
    )
    logger.info(chat_request.text)

    user_prompt = user_prompt_template_first.format(
        context=dialog_context, text=chat_request.text
    )
    try:
        completion = client.chat.completions.create(
            model=chat_request.model,
            messages=[
                {"role": "system", "content": system_prompt_initial},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )
        reply = completion.choices[0].message.content
        logger.info(reply)

        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, details=str(e)) from e
