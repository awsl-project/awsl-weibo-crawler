import re
import time
import random
import logging

from typing import List

from .db import find_all_awsl_producer, select_max_id, update_max_id, update_mblog, update_pic
from .http import WeiboSession, fetch_wb_headers
from .mq import MQPublisher
from .models.models import AwslProducer
from .pydantic_models import WeiboList, WeiboListItem
from .config import settings, WB_DATA_URL, WB_SHOW_URL


_logger = logging.getLogger(__name__)
WB_EMO = re.compile(r'\[awsl\]')


def _random_delay(base: float = 5.0, sigma: float = 2.0, min_delay: float = 2.0) -> None:
    delay = max(min_delay, random.gauss(base, sigma))
    if random.random() < 0.05:
        delay += random.uniform(3.0, 8.0)
    _logger.debug(f"Sleep {delay:.2f}s")
    time.sleep(delay)


class WbAwsl:

    def __init__(self, awsl_producer: AwslProducer, headers: dict, mq: MQPublisher) -> None:
        self.awsl_producer = awsl_producer
        self.uid = awsl_producer.uid
        self.max_id = int(awsl_producer.max_id) if awsl_producer.max_id else select_max_id(self.uid)
        self.keyword = awsl_producer.keyword or ""
        self.headers = headers
        self.mq = mq
        _logger.info(f"awsl init done {awsl_producer.uid}")

    @staticmethod
    def start() -> None:
        awsl_producers = find_all_awsl_producer()
        len_awsl_producers = len(awsl_producers)
        headers = fetch_wb_headers()
        mq = MQPublisher()

        try:
            for i, awsl_producer in enumerate(awsl_producers):
                _logger.info(f"start crawl {i}/{len_awsl_producers}: {awsl_producer.uid}")
                awsl = WbAwsl(awsl_producer, headers, mq)
                awsl.run()
                _random_delay(base=8.0, sigma=3.0, min_delay=4.0)
            _logger.info("awsl run all awsl_producers done")
        finally:
            mq.close()

    def run(self) -> None:
        _logger.info(f"awsl run: uid={self.uid} max_id={self.max_id}")
        old_max_id = self.max_id
        try:
            with WeiboSession(self.headers) as session:
                for wbdata in self.get_wbdata(old_max_id, session):
                    self.process_single(wbdata, session)
                    _random_delay()
        except Exception:
            _logger.exception(f"awsl run failed for uid={self.uid}")
        if self.max_id > old_max_id:
            update_max_id(self.uid, self.max_id)
            _logger.info(f"Updated max_id {old_max_id} -> {self.max_id} for uid={self.uid}")
        _logger.info(f"awsl run: uid={self.uid} done")

    def process_single(self, wbdata: WeiboListItem, session: WeiboSession) -> None:
        _logger.info(f"Processing wbdata id={wbdata.id} mblogid={wbdata.mblogid}")
        try:
            re_mblogid = update_mblog(self.awsl_producer, wbdata)
            _logger.info(f"update_mblog done, re_mblogid={re_mblogid}")
            re_wbdata = session.get(
                WB_SHOW_URL.format(re_mblogid)
            ) if re_mblogid else {}
            pic_count = len(re_wbdata.get("pic_ids", [])) if re_wbdata else 0
            _logger.info(f"Fetched detail for re_mblogid={re_mblogid} pics={pic_count}")
            self.mq.send2bot(self.awsl_producer, re_mblogid, re_wbdata)
            update_pic(wbdata, re_wbdata)
        except Exception:
            _logger.exception(f"Failed to process wbdata id={wbdata.id}")

    def get_wbdata(self, max_id: int, session: WeiboSession) -> List[WeiboListItem]:
        result = []
        for page in range(1, settings.max_page + 1):
            raw_data = session.get(url=WB_DATA_URL.format(self.uid, page))

            if raw_data is None:
                _logger.warning(f"No response for uid={self.uid} page={page}, skipping")
                continue

            try:
                wbdatas = WeiboList.model_validate(raw_data)
                wbdata_list = wbdatas.data.list if wbdatas.data else []
            except Exception:
                _logger.exception(f"Failed to parse weibo list for uid={self.uid} page={page}")
                continue

            _logger.info(f"Fetched {len(wbdata_list)} weibos for uid={self.uid} page={page}")

            if not wbdata_list:
                break

            stop = False
            for wbdata in wbdata_list:
                if wbdata.id <= max_id and page == 1:
                    _logger.info(f"Skipped old weibo id={wbdata.id} on page 1 for uid={self.uid}")
                    continue
                elif wbdata.id <= max_id:
                    _logger.info(f"Reached old weibo id={wbdata.id} <= max_id={max_id}, stopping uid={self.uid} page={page}")
                    stop = True
                    break
                if wbdata.id > self.max_id:
                    self.max_id = wbdata.id
                text_raw = WB_EMO.sub("", wbdata.text_raw)
                if self.keyword not in text_raw:
                    _logger.info(f"Skipped weibo id={wbdata.id} keyword not matched for uid={self.uid}")
                    continue
                _logger.info(f"Matched weibo id={wbdata.id} mblogid={wbdata.mblogid} for uid={self.uid} keyword='{self.keyword}'")
                result.append(wbdata)
            if stop:
                break
            _random_delay()
        _logger.info(f"Collected {len(result)} matched weibos for uid={self.uid}")
        return result
