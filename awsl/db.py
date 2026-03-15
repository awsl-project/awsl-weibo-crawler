import json
import logging

from typing import List

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

from .config import settings
from .models.models import AwslProducer, Mblog, Pic
from .pydantic_models import WeiboListItem

_logger = logging.getLogger(__name__)

_engine = None
_SessionFactory = None


def _get_session():
    global _engine, _SessionFactory
    if _SessionFactory is None:
        _engine = create_engine(
            settings.db_url,
            pool_size=1,
            max_overflow=0,
            pool_timeout=10,
            pool_recycle=1800,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )
        _SessionFactory = sessionmaker(bind=_engine)
    return _SessionFactory()


def select_max_id(uid: str) -> int:
    with _get_session() as session:
        mblog = session.query(func.max(Mblog.id)).filter(
            Mblog.uid == uid).one()
        return int(mblog[0]) if mblog and mblog[0] else 0


def update_max_id(uid: str, max_id: int) -> None:
    with _get_session() as session:
        session.query(AwslProducer).filter(
            AwslProducer.uid == uid
        ).update({
            AwslProducer.max_id: str(max_id)
        })
        session.commit()


def update_mblog(awsl_producer: AwslProducer, wbdata: WeiboListItem) -> str:
    origin_wbdata = wbdata.retweeted_status or wbdata
    if not origin_wbdata.user:
        _logger.warning(f"Skipped mblog write id={wbdata.id}: no user info, will still fetch detail")
        return origin_wbdata.mblogid if origin_wbdata.mblogid else ""
    _logger.info(f"awsl update db mblog awsl_producer={awsl_producer.name} id={wbdata.id} mblogid={wbdata.mblogid}")
    with _get_session() as session:
        mblog = Mblog(
            id=wbdata.id,
            uid=awsl_producer.uid,
            mblogid=wbdata.mblogid,
            re_id=origin_wbdata.id,
            re_mblogid=origin_wbdata.mblogid,
            re_user_id=origin_wbdata.user["id"],
            re_user=json.dumps(origin_wbdata.user)
        )
        session.merge(mblog)
        session.commit()
        _logger.info(f"Committed mblog id={wbdata.id} mblogid={wbdata.mblogid}")

    return origin_wbdata.mblogid


def update_pic(wbdata: WeiboListItem, re_wbdata: dict) -> None:
    if not re_wbdata:
        return
    pic_infos = re_wbdata.get("pic_infos", {})
    pic_ids = re_wbdata.get("pic_ids", [])
    if not pic_ids:
        return
    with _get_session() as session:
        existing = {
            row[0] for row in
            session.query(Pic.pic_id).filter(Pic.awsl_id == wbdata.id).all()
        }
        added = 0
        for sequence, pic_id in enumerate(pic_ids):
            if pic_id in existing:
                continue
            if pic_id not in pic_infos:
                _logger.warning(f"pic_id {pic_id} not found in pic_infos, skipping")
                continue
            session.add(Pic(
                awsl_id=wbdata.id,
                sequence=sequence,
                pic_id=pic_id,
                pic_info=json.dumps(pic_infos[pic_id]),
            ))
            added += 1
        session.commit()
        _logger.info(f"Committed {added} new pics for awsl_id={wbdata.id} (skipped {len(existing)} existing)")


def find_all_awsl_producer() -> List[AwslProducer]:
    with _get_session() as session:
        awsl_producers = session.query(
            AwslProducer
        ).filter(
            AwslProducer.in_verification.isnot(True)
        ).filter(
            AwslProducer.deleted.isnot(True)
        ).all()
        session.expunge_all()
        return awsl_producers
