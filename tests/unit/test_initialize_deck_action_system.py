"""InitializeDeckActionSystem 提交入口（叙事润色校验）的单元测试。"""

from ai_rpg.systems.initialize_deck_action_system import (
    _DeckCardEdit,
    _handle_submit_polish,
)


def test_valid_polish_stored() -> None:
    edits: list[_DeckCardEdit] = []
    msg = _handle_submit_polish(
        {"u1"}, edits, uuid="u1", name="断筋", description="一记短促的沉肩"
    )
    assert "已记录" in msg
    assert len(edits) == 1
    assert edits[0].uuid == "u1"
    assert edits[0].name == "断筋"


def test_unknown_uuid_rejected() -> None:
    edits: list[_DeckCardEdit] = []
    msg = _handle_submit_polish(
        {"u1"}, edits, uuid="u2", name="断筋", description="描述"
    )
    assert msg.startswith("错误")
    assert edits == []


def test_blank_fields_rejected() -> None:
    edits: list[_DeckCardEdit] = []
    assert _handle_submit_polish(
        {"u1"}, edits, uuid="u1", name="   ", description="描述"
    ).startswith("错误")
    assert _handle_submit_polish(
        {"u1"}, edits, uuid="u1", name="断筋", description="  "
    ).startswith("错误")
    assert edits == []


def test_trims_whitespace() -> None:
    edits: list[_DeckCardEdit] = []
    _handle_submit_polish(
        {"u1"}, edits, uuid="u1", name="  断筋  ", description="  描述  "
    )
    assert edits[0].name == "断筋"
    assert edits[0].description == "描述"
