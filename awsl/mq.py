import json
import logging

import pika

from .config import CHUNK_SIZE, WB_URL_PREFIX, settings
from .models.models import AwslProducer

_logger = logging.getLogger(__name__)


class MQPublisher:

    def __init__(self):
        self._connection: pika.BlockingConnection | None = None
        self._channel: pika.adapters.blocking_connection.BlockingChannel | None = None

    def _ensure_channel(self) -> bool:
        if not settings.pika_url or not settings.bot_queue:
            return False
        if self._channel is not None and self._channel.is_open:
            return True
        self.close()
        self._connection = pika.BlockingConnection(pika.URLParameters(settings.pika_url))
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=settings.bot_queue, durable=True)
        return True

    def close(self) -> None:
        if self._channel and self._channel.is_open:
            try:
                self._channel.close()
            except Exception:
                pass
        if self._connection and self._connection.is_open:
            try:
                self._connection.close()
            except Exception:
                pass
        self._channel = None
        self._connection = None

    def send2bot(self, awsl_producer: AwslProducer, re_mblogid: str, re_wbdata: dict) -> None:
        try:
            if not self._ensure_channel():
                return
            if "user" not in re_wbdata or "id" not in re_wbdata["user"]:
                _logger.warning(f"Missing user information in re_wbdata for mblogid {re_mblogid}")
                return
            if "mblogid" not in re_wbdata:
                _logger.warning(f"Missing mblogid in re_wbdata for re_mblogid {re_mblogid}")
                return
            wb_url = WB_URL_PREFIX.format(
                re_wbdata["user"]["id"], re_wbdata["mblogid"])
            pic_infos = re_wbdata.get("pic_infos", {})
            pic_ids = re_wbdata.get("pic_ids", [])
            source_screen_name = re_wbdata.get(
                "user", {}
            ).get(
                "screen_name"
            ) or awsl_producer.name
            for i in range(0, len(pic_ids), CHUNK_SIZE):
                self._channel.basic_publish(
                    exchange='',
                    routing_key=settings.bot_queue,
                    body=json.dumps({
                        "wb_url": wb_url,
                        "awsl_producer": source_screen_name,
                        "pics": [
                            pic_infos[pic_id]["original"]["url"]
                            for pic_id in pic_ids[i:i+CHUNK_SIZE]
                            if pic_id in pic_infos and "original" in pic_infos[pic_id]
                        ]
                    }),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                _logger.info(f"send bot_queue {pic_ids[i:i+CHUNK_SIZE]}")
            _logger.info(f"send to bot_queue re_mblogid {re_mblogid}")
        except Exception:
            _logger.exception(f"Failed to send message for re_mblogid={re_mblogid}")
