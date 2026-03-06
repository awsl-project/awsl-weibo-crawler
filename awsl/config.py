import os

from pydantic_settings import BaseSettings


WB_DATA_URL = "https://weibo.com/ajax/statuses/mymblog?uid={}&page="
WB_SHOW_URL = "https://weibo.com/ajax/statuses/show?id={}"
WB_PROFILE = "https://weibo.com/ajax/profile/info?uid={}"
WB_URL_PREFIX = "https://weibo.com/{}/{}"
CHUNK_SIZE = 9


class Settings(BaseSettings):
    awsl_api_url: str = ""
    awsl_api_token: str = ""
    max_page: int = 50
    db_url: str = ""
    pika_url: str = ""
    bot_queue: str = ""

    class Config:
        env_file = os.environ.get("ENV_FILE", ".env")


settings = Settings()
