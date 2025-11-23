from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    OPENAPI_KEY: str


@lru_cache()
def get_config():
    return BaseConfig()


config = get_config()
