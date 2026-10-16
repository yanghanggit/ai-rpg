"""AssembleDungeonDeckSystem 提交入口（词缀随牌设计）的单元测试。"""

from ai_rpg.models import Card
from ai_rpg.systems.assemble_dungeon_deck_system import (
    _DeckCardPick,
    _handle_submit_deck_card,
)


def _prototype_cards() -> dict[str, Card]:
    """带一个可设计槽（非空=有引导）的骨架卡，供提交校验用。"""
    card = Card(
        name="基础攻击",
        description="",
        damage=2,
        on_play_affixes=["[引导]:打出时取一个内建数值对目标造成伤害"],
    )
    return {"proto.attack": card}


def test_submit_deck_card_stores_affix_design() -> None:
    picks: list[_DeckCardPick] = []
    result = _handle_submit_deck_card(
        {"proto.attack"},
        _prototype_cards(),
        picks,
        prototype_id="proto.attack",
        name="断筋",
        description="一记短促的沉肩",
        cost=0,
        damage=4,
        on_play_affixes=["[断筋]:打出时对目标造成本卡 damage×2 的伤害"],
        on_hit_affixes=None,
        on_turn_end_affixes=None,
    )

    assert "已记录" in result
    assert len(picks) == 1
    pick = picks[0]
    assert pick.prototype_id == "proto.attack"
    assert pick.name == "断筋"
    assert (pick.cost, pick.damage) == (0, 4)
    assert pick.on_play_affixes == ["[断筋]:打出时对目标造成本卡 damage×2 的伤害"]
    assert pick.on_hit_affixes is None


def test_submit_deck_card_rejects_unknown_prototype() -> None:
    picks: list[_DeckCardPick] = []
    result = _handle_submit_deck_card(
        {"proto.attack"},
        _prototype_cards(),
        picks,
        prototype_id="proto.不存在",
        name="断筋",
        description="描述",
    )

    assert result.startswith("错误")
    assert picks == []


def test_submit_deck_card_rejects_invalid_affix() -> None:
    # 缺方括号：handler 应返回错误且不记录，让 agent 修正重提。
    picks: list[_DeckCardPick] = []
    result = _handle_submit_deck_card(
        {"proto.attack"},
        _prototype_cards(),
        picks,
        prototype_id="proto.attack",
        name="断筋",
        description="描述",
        on_play_affixes=["断筋:打出时对目标造成本卡 damage×2 的伤害"],
    )

    assert "错误" in result
    assert picks == []
