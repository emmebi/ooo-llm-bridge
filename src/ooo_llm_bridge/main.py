import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from openai import OpenAI

from ooo_llm_bridge.config import get_config
from ooo_llm_bridge.logging_conf import configure_logging
from ooo_llm_bridge.routers.segments import ask_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # setup logging
    configure_logging()
    logger.info("logging configured")

    # setup openai
    app.state.openai_client = OpenAI(api_key=get_config().OPENAPI_KEY)
    logger.info("OpenAI client initialized")

    yield

    app.state.openai_client = None
    logger.info("OpenAI client released")


app = FastAPI(lifespan=lifespan)
app.include_router(ask_router)
