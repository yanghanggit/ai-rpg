"""CraftGearItemActionSystem 提交入口（词缀设计校验）的单元测试。"""

from typing import Any, Dict, List

from src.ai_rpg.systems.craft_gear_item_action_system import (
    _CraftGearSpec,
    _handle_submit_gear,
)


def _card(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "target_type": "single",
        "damage": 2,
        "on_play_affixes": [],
        "on_hit_affixes": [],
        "on_turn_end_affixes": [],
    }
    base.update(overrides)
    return base


def test_valid_affix_design_accepted() -> None:
    results: List[_CraftGearSpec] = []
    reply = _handle_submit_gear(
        results,
        name="装备.燃骨刀",
        description="以兽骨为柄、燃痕为刃",
        card=_card(on_play_affixes=["[燃痕]:打出时对目标造成本卡 damage×2 的伤害"]),
    )

    assert not reply.startswith("错误")
    assert len(results) == 1
    assert results[0].on_play_affixes == ["[燃痕]:打出时对目标造成本卡 damage×2 的伤害"]


def test_affix_missing_field_anchor_rejected() -> None:
    results: List[_CraftGearSpec] = []
    reply = _handle_submit_gear(
        results,
        name="装备.燃骨刀",
        description="以兽骨为柄、燃痕为刃",
        card=_card(on_play_affixes=["[燃痕]:打出时对目标造成伤害"]),
    )

    assert reply.startswith("错误")
    assert "damage" in reply
    assert results == []


def test_placeholder_affix_rejected() -> None:
    results: List[_CraftGearSpec] = []
    reply = _handle_submit_gear(
        results,
        name="装备.燃骨刀",
        description="以兽骨为柄、燃痕为刃",
        card=_card(on_play_affixes=["[词缀名]:本次出牌产生何种效果"]),
    )

    assert reply.startswith("错误")
    assert results == []


def test_invalid_target_type_rejected() -> None:
    results: List[_CraftGearSpec] = []
    reply = _handle_submit_gear(
        results,
        name="装备.燃骨刀",
        description="以兽骨为柄、燃痕为刃",
        card=_card(target_type="boss"),
    )

    assert reply.startswith("错误")
    assert results == []
