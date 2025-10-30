from flask import Flask, request, jsonify
from openai import OpenAI
import os

# Load API key
with open(os.path.expanduser("~/.openai_key.txt")) as f:
    api_key = f.read().strip()


# Create OpenAI client
client = OpenAI(api_key=api_key)

app = Flask(__name__)

system_prompt = """
You are an helpful assistant; your purpose is to help the writer improve what he is writing. You will examine the text and provide an objective criticism of what is provided; your purpose is to help the writer improve, so writing on the writer's behalf will not fulfil the purpose; provide objective feedback on the text, and point the weak parts and the strong parts; provide examples of your suggestions, so that the writer can better understand what you mean. If the text is in italian, provide your answer in italian. If the text is in english, provide your answer in english."""

@app.route("/ask", methods=["POST"])
def ask():
    text = request.json.get("text", "")
    model = request.json.get("model", "gpt-4.1")
    print(text[:100])

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.7,
        )
        reply = completion.choices[0].message.content
        print(reply)

        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5000)
