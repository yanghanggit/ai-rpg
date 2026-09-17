"""GenerateSpoilsActionSystem 词缀「等量改写」回填逻辑的单元测试。"""

from src.ai_rpg.models import Card
from src.ai_rpg.systems.generate_spoils_action_system import (
    _SpoilsCardEdit,
    _apply_affix_edits,
)


def _card(**overrides: object) -> Card:
    base: dict[str, object] = {
        "name": "原型",
        "description": "原型描述",
        "on_play_affixes": ["[诅咒]:本次出牌对目标阵营施加减益"],
    }
    base.update(overrides)
    return Card.model_validate(base)


def _edit(card: Card, **overrides: object) -> _SpoilsCardEdit:
    base: dict[str, object] = {
        "uuid": card.uuid,
        "name": "改写名",
        "description": "改写描述",
    }
    base.update(overrides)
    return _SpoilsCardEdit.model_validate(base)


def test_equal_count_affixes_are_applied() -> None:
    card = _card()
    edit = _edit(card, on_play_affixes=["[病气缠身]:令同场者手脚发沉、力气散失"])

    assert _apply_affix_edits("角色.无名", card, edit) == 1
    assert card.on_play_affixes == ["[病气缠身]:令同场者手脚发沉、力气散失"]


def test_omitted_affixes_fall_back_to_prototype() -> None:
    card = _card()
    edit = _edit(card)  # 未提交任何词缀

    assert _apply_affix_edits("角色.无名", card, edit) == 0
    assert card.on_play_affixes == ["[诅咒]:本次出牌对目标阵营施加减益"]


def test_mismatched_count_falls_back_to_prototype() -> None:
    card = _card()
    edit = _edit(card, on_play_affixes=["[甲]:一", "[乙]:二"])

    assert _apply_affix_edits("角色.无名", card, edit) == 0
    assert card.on_play_affixes == ["[诅咒]:本次出牌对目标阵营施加减益"]


def test_empty_prototype_stays_empty() -> None:
    card = _card(on_play_affixes=[])
    edit = _edit(card)

    assert _apply_affix_edits("角色.无名", card, edit) == 0
    assert card.on_play_affixes == []
