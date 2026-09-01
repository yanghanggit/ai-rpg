"""卡牌原型数据库操作函数。

面向后续 Agent 工具的两级披露：
  - `list_card_prototype_index`：一级披露（id / domain / port / port_subtype / name / summary / tags），用于「选择核心」前纵览；
  - `get_card_prototype`：二级披露（含 guide 与 card_json），用于精读被选中的原型。
"""

import json
from typing import Dict, List, Optional
from loguru import logger
from .client import SessionLocal
from .card_prototype import CardPrototypeDB


############################################################################################################
def save_card_prototype(
    prototype_id: str,
    domain: str,
    port: str,
    port_subtype: str,
    name: str,
    summary: str,
    guide: str,
    card_json: str,
    tags: Optional[List[str]] = None,
) -> CardPrototypeDB:
    """保存或更新一个卡牌原型（按 prototype_id 幂等）。"""

    tags_json = json.dumps(tags or [], ensure_ascii=False)

    db = SessionLocal()
    try:
        existing = (
            db.query(CardPrototypeDB).filter_by(prototype_id=prototype_id).first()
        )
        if existing is not None:
            existing.domain = domain
            existing.port = port
            existing.port_subtype = port_subtype
            existing.name = name
            existing.summary = summary
            existing.guide = guide
            existing.card_json = card_json
            existing.tags_json = tags_json
            db.commit()
            db.refresh(existing)
            return existing

        proto = CardPrototypeDB(
            prototype_id=prototype_id,
            domain=domain,
            port=port,
            port_subtype=port_subtype,
            name=name,
            summary=summary,
            guide=guide,
            card_json=card_json,
            tags_json=tags_json,
        )
        db.add(proto)
        db.commit()
        db.refresh(proto)
        logger.info(f"✅ 卡牌原型已保存: {prototype_id}")
        return proto

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 保存卡牌原型失败: {e}")
        raise e

    finally:
        db.close()


############################################################################################################
def list_card_prototype_index(
    domain: Optional[str] = None,
    port: Optional[str] = None,
) -> List[Dict[str, object]]:
    """列出一级披露索引（不含 guide / card_json），可按 domain / port 过滤。"""

    db = SessionLocal()
    try:
        query = db.query(CardPrototypeDB)
        if domain:
            query = query.filter(CardPrototypeDB.domain == domain)
        if port:
            query = query.filter(CardPrototypeDB.port == port)
        rows = query.order_by(CardPrototypeDB.created_at).all()
        return [
            {
                "prototype_id": row.prototype_id,
                "domain": row.domain,
                "port": row.port,
                "port_subtype": row.port_subtype,
                "name": row.name,
                "summary": row.summary,
                "tags": json.loads(row.tags_json),
            }
            for row in rows
        ]
    finally:
        db.close()


############################################################################################################
def get_card_prototype(prototype_id: str) -> CardPrototypeDB:
    """按 prototype_id 获取单个卡牌原型（含 guide 与 card_json）。"""

    db = SessionLocal()
    try:
        proto = db.query(CardPrototypeDB).filter_by(prototype_id=prototype_id).first()
        if proto is None:
            raise ValueError(f"卡牌原型 '{prototype_id}' 不存在")
        return proto
    finally:
        db.close()
