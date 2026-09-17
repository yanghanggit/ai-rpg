"""AssembleDeckSystem 提交入口（词缀随牌设计）的单元测试。"""

from src.ai_rpg.systems.assemble_deck_system import (
    _DeckCardPick,
    _handle_submit_deck_card,
)


def test_submit_deck_card_stores_affix_design() -> None:
    picks: list[_DeckCardPick] = []
    result = _handle_submit_deck_card(
        {"proto.attack"},
        picks,
        prototype_id="proto.attack",
        name="断筋",
        description="一记短促的沉肩",
        on_play_affixes=["[断筋]:打出时对目标造成本卡 damage×2 的伤害"],
        on_hit_affixes=None,
        on_turn_end_affixes=None,
    )

    assert "已记录" in result
    assert len(picks) == 1
    pick = picks[0]
    assert pick.prototype_id == "proto.attack"
    assert pick.name == "断筋"
    assert pick.on_play_affixes == ["[断筋]:打出时对目标造成本卡 damage×2 的伤害"]
    assert pick.on_hit_affixes is None


def test_submit_deck_card_rejects_unknown_prototype() -> None:
    picks: list[_DeckCardPick] = []
    result = _handle_submit_deck_card(
        {"proto.attack"},
        picks,
        prototype_id="proto.不存在",
        name="断筋",
        description="描述",
    )

    assert result.startswith("错误")
    assert picks == []
