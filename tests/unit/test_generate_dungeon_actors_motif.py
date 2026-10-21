"""怪物 motif 生成链路单测：工具 schema 必带 motif，handler 落进 draft。

LLM 会话本身在模块边界之外，这里只测「契约里有 motif → handler 记录 motif」这一段。
"""

from ai_rpg.models import DungeonRoomDraft
from ai_rpg.systems.generate_dungeon_actors_system import (
    _ActorsResult,
    _build_record_dungeon_actor_tool,
    _handle_record_dungeon_actor,
    missing_motif_sections,
)

_ROOM = DungeonRoomDraft(
    room_name="房间.荒径",
    room_type="combat",
    profile="泥泞的窄道",
    actor_count=2,
)


def test_record_actor_tool_requires_motif() -> None:
    """motif 与 profile 同级：schema 里有字段、且在 required 里。"""
    tool = _build_record_dungeon_actor_tool([_ROOM])
    parameters = tool.function.parameters

    assert "motif" in parameters["properties"]
    assert "motif" in parameters["required"]
    assert "场景中立" in parameters["properties"]["motif"]["description"]


_QUOTAS = {_ROOM.room_name: 2}


def test_handler_records_motif() -> None:
    result = _ActorsResult()

    _handle_record_dungeon_actor(
        result,
        _QUOTAS,
        room_name=_ROOM.room_name,
        actor_name="怪物.泥行者",
        profile="第一人称扮演",
        base_body="第三人称外观",
        motif="**母题**: 泥下的等待",
    )

    assert len(result.actors) == 1
    assert result.actors[0].motif == "**母题**: 泥下的等待"


def test_handler_normalizes_escaped_newlines() -> None:
    """模型偶发把换行写成字面 `\\n`：handler 还原成真实换行，供提示词分节。"""
    result = _ActorsResult()

    _handle_record_dungeon_actor(
        result,
        _QUOTAS,
        room_name=_ROOM.room_name,
        actor_name="怪物.泥行者",
        profile="p",
        base_body="b",
        motif="**母题**: 泥下的等待\\n**意象**: 湿泥、干草",
    )

    assert result.actors[0].motif == "**母题**: 泥下的等待\n**意象**: 湿泥、干草"


def test_handler_rejects_unknown_room() -> None:
    """未知房间（含开场房间）不入账，只回错误文本让 LLM 自纠。"""
    result = _ActorsResult()

    reply = _handle_record_dungeon_actor(
        result, _QUOTAS, "房间.不存在的", "怪物.泥行者", "p", "b"
    )

    assert "不是本次需要怪物的战斗房间" in reply
    assert result.actors == []


def test_handler_rejects_overflow_actor() -> None:
    """超过房间配额的第 3 个怪物被拒，前两个照常入账。"""
    result = _ActorsResult()
    for index in (1, 2):
        _handle_record_dungeon_actor(
            result, _QUOTAS, _ROOM.room_name, f"怪物.{index}", "p", "b"
        )

    reply = _handle_record_dungeon_actor(
        result, _QUOTAS, _ROOM.room_name, "怪物.多余的", "p", "b"
    )

    assert "只需要 2 个怪物，已满额" in reply
    assert [actor.actor_name for actor in result.actors] == ["怪物.1", "怪物.2"]


def test_handler_tolerates_missing_motif() -> None:
    """旧口径（模型没传 motif）不报错，落成空串，后续按「无锚点」回退。"""
    result = _ActorsResult()

    _handle_record_dungeon_actor(
        result, _QUOTAS, _ROOM.room_name, "怪物.泥行者", "p", "b"
    )

    assert result.actors[0].motif == ""


def test_missing_motif_sections_reports_gaps() -> None:
    """只告警、不改行为：空锚点算全缺，缺哪一节就报哪一节。"""
    assert missing_motif_sections("") == ["母题", "意象"]
    assert missing_motif_sections("**母题**: 泥下的等待") == ["意象"]
    assert missing_motif_sections("**母题**: 泥下的等待\n**意象**: 湿泥、干草") == []
