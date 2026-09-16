"""默认牌单数据库操作函数。

单例语义：整表仅维护一行默认牌库配置。
  - `save_deck_build`：写入 / 更新这套默认牌单（幂等）；
  - `get_default_deck_card_jsons`：按牌单顺序一次性取出各张卡的 card_json（含重复），
    供 assemble_deck_system.make_default_deck_cards 直接物化。
"""

import json
from typing import List
from loguru import logger
from .client import SessionLocal
from .card_prototype import CardPrototypeDB
from .deck_build import DeckBuildDB


############################################################################################################
def save_deck_build(card_prototype_ids: List[str]) -> DeckBuildDB:
    """写入 / 更新默认牌单（单例：始终复用第一行，按 id 列表覆盖）。"""

    card_prototype_ids_json = json.dumps(card_prototype_ids, ensure_ascii=False)

    db = SessionLocal()
    try:
        existing = db.query(DeckBuildDB).first()
        if existing is not None:
            existing.card_prototype_ids_json = card_prototype_ids_json
            db.commit()
            db.refresh(existing)
            return existing

        build = DeckBuildDB(card_prototype_ids_json=card_prototype_ids_json)
        db.add(build)
        db.commit()
        db.refresh(build)
        logger.info(f"✅ 默认牌单已保存: {len(card_prototype_ids)} 张")
        return build

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 保存默认牌单失败: {e}")
        raise e

    finally:
        db.close()


############################################################################################################
def get_default_deck_card_jsons() -> List[str]:
    """按默认牌单顺序返回各张卡的 card_json（允许重复）。

    单例语义：读取唯一一行牌单；牌单缺失、或引用了不存在的原型时抛错。
    """

    db = SessionLocal()
    try:
        build = db.query(DeckBuildDB).first()
        if build is None:
            raise ValueError("默认牌单不存在：请先运行 scripts/setup_demo.py 灌库")

        prototype_ids: List[str] = json.loads(build.card_prototype_ids_json)

        # 一次查询取出全部被引用原型，再按牌单顺序（含重复）重建结果
        rows = (
            db.query(CardPrototypeDB)
            .filter(CardPrototypeDB.prototype_id.in_(prototype_ids))
            .all()
        )
        card_json_by_id = {row.prototype_id: row.card_json for row in rows}

        card_jsons: List[str] = []
        for prototype_id in prototype_ids:
            card_json = card_json_by_id.get(prototype_id)
            if card_json is None:
                raise ValueError(f"默认牌单引用的原型不存在: {prototype_id}")
            card_jsons.append(card_json)

        return card_jsons

    finally:
        db.close()
