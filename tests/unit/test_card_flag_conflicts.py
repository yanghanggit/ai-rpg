"""Card 布尔标志硬约束（`_reject_flag_conflicts`）的单元测试。"""

import pytest

from ai_rpg.models import Card, TargetType


def test_transferable_with_self_target_raises() -> None:
    """`self_target` 与 `transferable` 互斥：构造即失败。"""
    with pytest.raises(ValueError, match="互斥"):
        Card(name="自缚", description="", transferable=True, self_target=True)


def test_transferable_with_single_target_is_allowed() -> None:
    """自传递复制走显式目标：transferable + SINGLE + 不锁自身，合法。"""
    card = Card(
        name="投掷",
        description="",
        transferable=True,
        self_target=False,
        target_type=TargetType.SINGLE,
    )
    assert card.transferable is True
    assert card.self_target is False


def test_self_target_without_transferable_is_allowed() -> None:
    """防御类锁定自身的牌不受影响。"""
    card = Card(name="防御", description="", self_target=True)
    assert card.self_target is True
    assert card.transferable is False
