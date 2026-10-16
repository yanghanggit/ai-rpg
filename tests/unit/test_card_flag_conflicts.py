"""Card 目标类型（`TargetType.SELF`）字段组合的单元测试。"""

from ai_rpg.models import Card, TargetType


def test_self_type_ignores_target_selection() -> None:
    """`SELF` 是合法目标类型，锁定出牌者本人。"""
    card = Card(name="防御", description="", target_type=TargetType.SELF)
    assert card.target_type == TargetType.SELF


def test_self_type_with_transferable_is_allowed() -> None:
    """`SELF` 解析出出牌者本人，可与 `transferable` 同开实现自传递复制。"""
    card = Card(
        name="回环",
        description="",
        transferable=True,
        target_type=TargetType.SELF,
    )
    assert card.transferable is True
    assert card.target_type == TargetType.SELF
