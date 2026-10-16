"""AssembleDungeonDeckSystem 选型入口的单元测试。

设计契约（submit_card / 词缀校验 / 落地）已统一由 card_design 引擎承担，
覆盖在 tests/unit/test_card_design.py；本文件只测牌库特有的「选型」步骤。
"""

from ai_rpg.systems.assemble_dungeon_deck_system import (
    _DeckSelection,
    _handle_select_deck_cards,
)

VALID = {"proto.attack", "proto.block", "proto.burst", "proto.heal", "proto.weaken"}


def test_select_deck_cards_stores_ids_and_allows_duplicates() -> None:
    selection = _DeckSelection()
    ids = ["proto.attack", "proto.attack", "proto.burst", "proto.heal", "proto.block"]

    result = _handle_select_deck_cards(selection, VALID, ids)

    assert "已记录" in result
    assert selection.prototype_ids == ids


def test_select_deck_cards_rejects_wrong_count() -> None:
    selection = _DeckSelection()

    result = _handle_select_deck_cards(selection, VALID, ["proto.attack"])

    assert result.startswith("错误")
    assert selection.prototype_ids == []


def test_select_deck_cards_rejects_unknown_id() -> None:
    selection = _DeckSelection()
    ids = ["proto.attack", "proto.attack", "proto.burst", "proto.heal", "proto.不存在"]

    result = _handle_select_deck_cards(selection, VALID, ids)

    assert result.startswith("错误")
    assert selection.prototype_ids == []
