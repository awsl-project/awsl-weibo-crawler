import logging
import random
import time

import httpx

from .config import FALLBACK_HEADERS, settings

_logger = logging.getLogger(__name__)


class WeiboSession:
    """Persistent HTTP session with anti-detection: jitter, retry, cookie merging."""

    def __init__(self, headers: dict, timeout: float = 30.0, max_retries: int = 3):
        self._headers = {**FALLBACK_HEADERS, **headers}
        self._timeout = timeout
        self._max_retries = max_retries
        self._last_request_time = 0.0
        self._client: httpx.Client | None = None

    def __enter__(self) -> "WeiboSession":
        self._client = httpx.Client(
            headers=self._headers,
            follow_redirects=True,
            timeout=httpx.Timeout(self._timeout),
        )
        return self

    def __exit__(self, *args) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def _jitter_delay(self) -> None:
        elapsed = time.time() - self._last_request_time
        base_delay = max(0, 1.0 - elapsed)
        jitter = max(0, random.gauss(0.3, 0.15))
        if random.random() < 0.05:
            jitter += random.uniform(2.0, 5.0)
        sleep_time = base_delay + jitter
        if sleep_time > 0:
            _logger.debug(f"Request jitter delay: {sleep_time:.2f}s")
            time.sleep(sleep_time)

    def get(self, url: str) -> dict | None:
        if self._client is None:
            raise RuntimeError("WeiboSession must be used as a context manager")
        self._jitter_delay()
        last_exc = None

        for attempt in range(self._max_retries):
            try:
                resp = self._client.get(url)
                self._last_request_time = time.time()

                for name, value in resp.cookies.items():
                    if value:
                        self._client.cookies.set(name, value)

                if resp.status_code in (429, 500, 502, 503, 504):
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    _logger.warning(f"HTTP {resp.status_code} on {url[:60]}, retrying in {wait:.1f}s ({attempt + 1}/{self._max_retries})")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                text = resp.text
                if text.startswith("<"):
                    _logger.warning(f"Received HTML instead of JSON from {url[:60]}")
                    return None
                return resp.json()

            except httpx.HTTPStatusError as exc:
                _logger.warning(f"HTTP {exc.response.status_code} on {url[:60]}: {exc}")
                return None

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                wait = (2 ** attempt) + random.uniform(0, 1)
                _logger.warning(f"Request error: {exc}, retrying in {wait:.1f}s ({attempt + 1}/{self._max_retries})")
                time.sleep(wait)

        _logger.error(f"Request failed after {self._max_retries} retries: {last_exc}")
        return None


def fetch_wb_headers() -> dict:
    try:
        res = httpx.get(
            url=f"{settings.awsl_api_url}/admin/wb_headers",
            headers={"Authorization": f"Bearer {settings.awsl_api_token.get_secret_value()}"},
            timeout=10.0,
        )
        res.raise_for_status()
        headers = res.json()
        _logger.info(f"Fetched wb_headers from API, keys: {list(headers.keys())}")
        return headers
    except Exception:
        _logger.exception("Failed to fetch wb_headers from API")
        return {}
