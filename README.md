# Description

This is a small bridge between LibreOffice/OpenOffice and LLM. At the moment it is working with OpenAI API, but in my dreams I would like to enable differnt LLMs, both local and remote.

I wrote this prototype (with the help of ChatGPT) to automate my workflow when writing fiction.

When I write, I often submit what I have written to ChatGPT to get a feedback. I usually aim at having feedback rather than having the LLM rewrite the things for me.

This tool is currently composed of two parts:
* a trivial REST bridge, which receives the text to be reviewed, from OOO, submits to the LLM and returns back the reply (or the error)
* a python macro running inside OOO, which sends to the REST bridge either the whole text up to the cursor or the text selected; once the reply arrives, it shows it in a separate dialog. The dialog is not modal, and the request happens on a different thread, so that OOO is not blocked while waiting for the answer.

Note that the few comments are in italian; I plan to fix this as soon as possible.

# Installation

* install the required libraries from requirements.txt
* copy the openai.py in the script directory for your LibreOffice; the exact location varies depending on the OS; on Windows is %AppData%\Roaming\LibreOffice\4\user\Scripts\python
* start the bridge with something like
```
python main.py
```

The bridge expects to find your API key in .openai_key.txt. 

# Future plans

* select/use different prompts
* add more back-ends
* create an add-on instead of simple macros
* remove the need of a separate bridge
