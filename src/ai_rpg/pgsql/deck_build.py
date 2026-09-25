"""默认牌单 ORM 模型定义。

单例表：整个数据库仅维护一套默认牌库配置，作为牌库组建失败时的兜底牌库。
"""

from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import UUIDBase


class DeckBuildDB(UUIDBase):
    """默认牌单表 - 单例存储一套默认牌库配置。

    `card_prototype_ids_json` 为有序的原型 id 数组（JSON），重复项即副本份数，
    对应 demo/card_prototypes.py 的 `DEFAULT_DECK_BUILD`。
    """

    __tablename__ = "deck_builds"

    # 有序原型 id 列表（JSON 数组字符串，如 ["proto.attack","proto.attack","proto.defense"]）
    card_prototype_ids_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
