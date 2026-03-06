import re
import time
import logging

from typing import Generator

from .tools import Tools
from .models.models import AwslProducer
from .pydantic_models import WeiboList, WeiboListItem
from .config import settings, WB_DATA_URL, WB_SHOW_URL


_logger = logging.getLogger(__name__)
WB_EMO = re.compile(r'\[awsl\]')


class WbAwsl(object):

    def __init__(self, awsl_producer: AwslProducer) -> None:
        self.awsl_producer = awsl_producer
        self.uid = awsl_producer.uid
        self.max_id = int(awsl_producer.max_id) if awsl_producer.max_id else Tools.select_max_id(self.uid)
        self.url = WB_DATA_URL.format(awsl_producer.uid)
        self.keyword = awsl_producer.keyword
        self.headers = Tools.fetch_wb_headers()
        _logger.info("awsl init done %s" % awsl_producer.uid)

    @staticmethod
    def start() -> None:
        awsl_producers = Tools.find_all_awsl_producer()
        len_awsl_producers = len(awsl_producers)

        for i, awsl_producer in enumerate(awsl_producers):
            _logger.info(f"start crawl {i}/{len_awsl_producers}: {awsl_producer.uid}")
            awsl = WbAwsl(awsl_producer)
            awsl.run()
            time.sleep(10)

        _logger.info("awsl run all awsl_producers done")

    def run(self) -> None:
        """
        获取微博数据并处理
        """
        _logger.info("awsl run: uid=%s max_id=%s" % (self.uid, self.max_id))
        try:
            for wbdata in self.get_wbdata(self.max_id):
                self.process_single(wbdata)
                time.sleep(10)
        except Exception as e:
            _logger.exception(e)
        _logger.info("awsl run: uid=%s done" % self.uid)

    def process_single(self, wbdata: WeiboListItem) -> None:
        """
        处理单条微博
        """
        if wbdata.id > self.max_id:
            Tools.update_max_id(self.uid, wbdata.id)
            self.max_id = wbdata.id
        try:
            re_mblogid = Tools.update_mblog(self.awsl_producer, wbdata)
            re_wbdata = Tools.wb_get(
                WB_SHOW_URL.format(re_mblogid), self.headers
            ) if re_mblogid else {}
            Tools.send2bot(self.awsl_producer, re_mblogid, re_wbdata)
            Tools.update_pic(wbdata, re_wbdata)
        except Exception as e:
            _logger.exception(e)

    def get_wbdata(self, max_id: int) -> Generator[WeiboListItem, None, None]:
        """
        获取微博列表数据
        """
        for page in range(1, settings.max_page):
            raw_data = Tools.wb_get(url=self.url + str(page), headers=self.headers)

            try:
                wbdatas = WeiboList.model_validate(raw_data)
                wbdata_list = wbdatas.data.list if wbdatas and wbdatas.data else []
            except Exception as e:
                _logger.exception(e)
                continue

            if not wbdata_list:
                return

            for wbdata in wbdata_list:
                if wbdata.id <= max_id and page == 1:
                    continue
                elif wbdata.id <= max_id:
                    return
                # TODO: 正则是不是更好
                text_raw = WB_EMO.sub("", wbdata.text_raw)
                if self.keyword not in text_raw:
                    continue
                yield wbdata
            time.sleep(10)
