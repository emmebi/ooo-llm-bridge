# Description

This is a small bridge between LibreOffice/OpenOffice and an LLM. At the moment it works with the OpenAI API, but the goal is to support different LLMs, both local and remote.

I wrote this prototype (with the help of ChatGPT) to automate my workflow when writing fiction.

When I write, I often submit what I have written to ChatGPT to get feedback. I usually aim at having feedback rather than having the LLM rewrite things for me.

This tool is composed of two parts:

* A REST bridge (`src/ooo_llm_bridge/`), which receives the text to be reviewed from LibreOffice, submits it to the LLM, and returns the reply. It is built with FastAPI and the OpenAI Python SDK.
* A Python macro (`ooo-macros/openai.py`) running inside LibreOffice Writer, which:
  * Sends either the selected text or everything up to the cursor to the bridge
  * Collects all existing comment threads in the document and includes them in the request, so the LLM can read the ongoing editorial conversation
  * Receives a structured JSON response containing new observations and replies to existing threads
  * Inserts new observations directly into the document as Writer annotations, anchored to the relevant text snippets
  * Appends the LLM's replies inside existing comment threads and optionally marks threads as resolved
  * Shows the raw response in a non-modal dialog while the request is in progress
  * Runs the HTTP request on a background thread so LibreOffice is not blocked while waiting

The LLM acts as a fiction editor named "Anacleto". It responds in the same language as the text, tracks open and resolved editorial issues across multiple invocations, and limits the total number of open issues to keep feedback actionable.

# Installation

* Install the required libraries:
  ```
  pip install -r requirements.txt
  ```
* Copy `ooo-macros/openai.py` to LibreOffice's Python scripts directory. The exact location varies by OS; on Windows it is:
  ```
  %AppData%\Roaming\LibreOffice\4\user\Scripts\python
  ```
* Create a `.env` file in the `src/` directory (see `.env.example`) with your OpenAI API key:
  ```
  OPENAPI_KEY=your-openai-api-key
  ```
* Start the bridge from within the `src/` directory:
  ```
  uvicorn ooo_llm_bridge.main:app
  ```

# Future plans

* Select/use different prompts
* Add more back-ends
* Create an add-on instead of simple macros
* Remove the need for a separate bridge
