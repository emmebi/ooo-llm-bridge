from fastapi import Request


def get_openai_client(request: Request):
    return request.app.state.openai_client
