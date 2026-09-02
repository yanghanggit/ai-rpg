"""卡牌原型 ORM 模型定义。"""

from datetime import datetime
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import UUIDBase


class CardPrototypeDB(UUIDBase):
    """卡牌原型表 - 存储与游戏内容解耦的指导性卡牌原型，供 Agent 检索后「选择核心 + 润色」。"""

    __tablename__ = "card_prototypes"

    # 稳定检索键（对应 demo/card_prototypes.py 的 meta.prototype_id）
    prototype_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )

    # 应用场景（手牌 / 装备），供按域检索（工坊合成按「装备」过滤）
    card_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)

    # 三端大类（攻击端 / 防御端 / 运转端）
    archetype: Mapped[str] = mapped_column(String(50), index=True, nullable=False)

    # 三端小类（前端伤害 / 成长性伤害 / 铺垫性攻击支持 / 前端防御 / 成长性防御 / 特殊防御机制）
    archetype_subtype: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )

    # 原型名（教学性文本，不耦合游戏内容）
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 一级披露：一句话摘要，供列表 / 索引
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    # 二级披露：完整字段语义与设计指导
    guide: Mapped[str] = mapped_column(Text, nullable=False)

    # 检索标签（JSON 数组字符串，如 ["装备", "on_play_affixes", "damage"]）
    keywords_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # 原型 Card 的完整字段快照（JSON），供「选择核心」后反序列化为 Card 再润色
    card_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
