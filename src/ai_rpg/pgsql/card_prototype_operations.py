"""卡牌原型数据库操作函数。

面向后续 Agent 工具的两级披露：
  - `list_card_prototype_index`：一级披露（id / card_type / archetype / archetype_subtype / name / summary / keywords），用于「选择核心」前纵览；
  - `get_card_prototype`：二级披露（含 design 与 card_json），用于精读被选中的原型。
"""

import json
from typing import List, Optional, TypedDict

from loguru import logger

from .card_prototype import CardPrototypeDB
from .client import SessionLocal


############################################################################################################
class CardPrototypeIndexEntry(TypedDict):
    """一级披露索引条目（`list_card_prototype_index` 的返回值元素）。"""

    prototype_id: str
    card_type: str
    tier: str
    archetype: str
    archetype_subtype: str
    name: str
    summary: str
    keywords: List[str]


############################################################################################################
def save_card_prototype(
    prototype_id: str,
    card_type: str,
    archetype: str,
    archetype_subtype: str,
    name: str,
    summary: str,
    design: str,
    card_json: str,
    keywords: Optional[List[str]] = None,
    tier: str = "normal",
) -> CardPrototypeDB:
    """保存或更新一个卡牌原型（按 prototype_id 幂等）。"""

    keywords_json = json.dumps(keywords or [], ensure_ascii=False)

    db = SessionLocal()
    try:
        existing = (
            db.query(CardPrototypeDB).filter_by(prototype_id=prototype_id).first()
        )
        if existing is not None:
            existing.card_type = card_type
            existing.tier = tier
            existing.archetype = archetype
            existing.archetype_subtype = archetype_subtype
            existing.name = name
            existing.summary = summary
            existing.design = design
            existing.card_json = card_json
            existing.keywords_json = keywords_json
            db.commit()
            db.refresh(existing)
            return existing

        proto = CardPrototypeDB(
            prototype_id=prototype_id,
            card_type=card_type,
            tier=tier,
            archetype=archetype,
            archetype_subtype=archetype_subtype,
            name=name,
            summary=summary,
            design=design,
            card_json=card_json,
            keywords_json=keywords_json,
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
def delete_card_prototypes(prototype_ids: List[str]) -> int:
    """删除指定的卡牌原型，返回实际删除行数（开发 / 测试用）。

    与 `save_card_prototype` 配套：`flush_card_prototypes` 用它把库里不在目标集合中的
    原型清掉，从而让 `generate-spoils` 的随机抽样退化为确定抽样（定点测试）。
    """

    if not prototype_ids:
        return 0

    db = SessionLocal()
    try:
        rows = (
            db.query(CardPrototypeDB)
            .filter(CardPrototypeDB.prototype_id.in_(prototype_ids))
            .all()
        )
        for row in rows:
            db.delete(row)
        db.commit()
        return len(rows)
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 删除卡牌原型失败: {e}")
        raise e
    finally:
        db.close()


############################################################################################################
def list_card_prototype_index(
    card_type: Optional[str] = None,
    archetype: Optional[str] = None,
    include_basic: bool = False,
) -> List[CardPrototypeIndexEntry]:
    """列出一级披露索引（不含 design / card_json），可按 card_type / archetype 过滤。

    默认隐藏 `tier="basic"` 的基础牌：它们是开局保底发放、不参与「选型」的牌；
    需要完整清单（运维 / 诊断）时传 `include_basic=True`。
    """

    db = SessionLocal()
    try:
        query = db.query(CardPrototypeDB)
        if card_type:
            query = query.filter(CardPrototypeDB.card_type == card_type)
        if archetype:
            query = query.filter(CardPrototypeDB.archetype == archetype)
        if not include_basic:
            query = query.filter(CardPrototypeDB.tier != "basic")
        rows = query.order_by(CardPrototypeDB.created_at).all()
        return [
            {
                "prototype_id": row.prototype_id,
                "card_type": row.card_type,
                "tier": row.tier,
                "archetype": row.archetype,
                "archetype_subtype": row.archetype_subtype,
                "name": row.name,
                "summary": row.summary,
                "keywords": json.loads(row.keywords_json),
            }
            for row in rows
        ]
    finally:
        db.close()


############################################################################################################
def get_card_prototype(prototype_id: str) -> CardPrototypeDB:
    """按 prototype_id 获取单个卡牌原型（含 design 与 card_json）。"""

    db = SessionLocal()
    try:
        proto = db.query(CardPrototypeDB).filter_by(prototype_id=prototype_id).first()
        if proto is None:
            raise ValueError(f"卡牌原型 '{prototype_id}' 不存在")
        return proto
    finally:
        db.close()


############################################################################################################
def get_card_prototype_by_name(
    name: str,
    card_type: Optional[str] = None,
) -> CardPrototypeDB:
    """按 name 获取单个卡牌原型（含 design 与 card_json）。"""

    db = SessionLocal()
    try:
        query = db.query(CardPrototypeDB).filter(CardPrototypeDB.name == name)
        if card_type:
            query = query.filter(CardPrototypeDB.card_type == card_type)
        proto = query.first()
        if proto is None:
            raise ValueError(
                f"卡牌原型 '{name}' 不存在"
                + (f"（card_type={card_type!r}）" if card_type else "")
            )
        return proto
    finally:
        db.close()
