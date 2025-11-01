import os

from fastapi import APIRouter, FastAPI, HTTPException
from openai import OpenAI

from ooo_llm_bridge.models.message import ChatRequest, ChatResponse

# Load API key
with open(os.path.expanduser("~/.openai_key.txt")) as f:
    api_key = f.read().strip()


# Create OpenAI client
client = OpenAI(api_key=api_key)


ask_router = APIRouter()

system_prompt = """
You are an helpful assistant; your purpose is to help the writer improve what he is writing. You will examine the text and provide an objective criticism of what is provided; your purpose is to help the writer improve, so writing on the writer's behalf will not fulfil the purpose; provide objective feedback on the text, and point the weak parts and the strong parts; provide examples of your suggestions, so that the writer can better understand what you mean. If the text is in italian, provide your answer in italian. If the text is in english, provide your answer in english."""


@ask_router.post(path="/ask")
async def ask(chat_request: ChatRequest, response_model=ChatResponse):
    print(chat_request.text[:100])

    try:
        completion = client.chat.completions.create(
            model=chat_request.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chat_request.text},
            ],
            temperature=0.7,
        )
        reply = completion.choices[0].message.content
        print(reply)

        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, details=str(e)) from e


app = FastAPI()
app.include_router(ask_router)
