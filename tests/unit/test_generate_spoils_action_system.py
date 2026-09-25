"""GenerateSpoilsActionSystem 的候选物化、prompt 组装与提交暂存的单元测试。"""

from ai_rpg.models import Card
from ai_rpg.systems.generate_spoils_action_system import (
    _Candidate,
    _format_card_for_prompt,
    _handle_submit_spoils_card,
    _SpoilsCardEdit,
)


def _candidate() -> _Candidate:
    card = Card(
        name="骨架卡",
        description="",
        damage=2,
        block=1,
        retain=True,
        on_turn_end_affixes=[
            "[中毒]:回合结束时对非 source 者结算本卡 damage×1 的持续伤害"
        ],
    )
    return _Candidate(
        card=card,
        archetype="攻击端",
        archetype_subtype="成长性伤害",
        summary="摘要",
        guide="指导",
    )


def test_format_card_includes_guide_and_skeleton() -> None:
    text = _format_card_for_prompt(_candidate())

    assert "攻击端 / 成长性伤害" in text
    assert "摘要" in text
    assert "指导" in text
    assert "damage=2" in text
    assert "retain=True" in text
    # 原型词缀作为回退参考展示
    assert "on_turn_end_affixes（原型回退参考，需重设计）" in text


def test_handle_submit_stores_all_design_fields() -> None:
    edits: list[_SpoilsCardEdit] = []
    _handle_submit_spoils_card(
        edits,
        uuid="u-1",
        name="朱批",
        description="落款",
        on_play_affixes=["[朱批]:打出时对目标造成本卡 damage×1 的伤害"],
        on_hit_affixes=None,
        on_turn_end_affixes=[
            "[余墨]:回合结束时对非 source 者结算本卡 damage×1 的持续伤害"
        ],
    )

    assert len(edits) == 1
    edit = edits[0]
    assert edit.uuid == "u-1"
    assert edit.name == "朱批"
    assert edit.on_play_affixes == ["[朱批]:打出时对目标造成本卡 damage×1 的伤害"]
    assert edit.on_hit_affixes is None
