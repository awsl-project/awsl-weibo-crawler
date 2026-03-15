import os

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


WB_DATA_URL = "https://weibo.com/ajax/statuses/mymblog?uid={}&page={}"
WB_SHOW_URL = "https://weibo.com/ajax/statuses/show?id={}"
WB_URL_PREFIX = "https://weibo.com/{}/{}"
CHUNK_SIZE = 9

BASE_URL = "https://weibo.com"

FALLBACK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": f"{BASE_URL}/",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=os.environ.get("ENV_FILE", ".env"))

    awsl_api_url: str = ""
    awsl_api_token: SecretStr = SecretStr("")
    max_page: int = 50
    db_url: str = ""
    pika_url: str = ""
    bot_queue: str = ""


settings = Settings()
