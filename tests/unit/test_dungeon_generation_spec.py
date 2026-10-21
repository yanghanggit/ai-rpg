"""副本生成显式规格（调测用）单测：结构校验、入口接线、以及「正式 API 无法作弊」。

规格只经由 `GenerateDungeonAction.spec` 传递；本文件验证三件事：
- 规格自洽性校验与默认值解析；
- 开发入口 `activate_generate_dungeon(spec=...)` 的写入与拒绝；
- 正式 API 的请求模型里**没有**任何规格字段（线上无法传递）。
"""

from typing import Any, List, cast
from unittest.mock import MagicMock

import pytest

from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    DEFAULT_DUNGEON_ROOM_COUNT,
    DEFAULT_MONSTERS_PER_COMBAT_ROOM,
    DEFAULT_OPENING_ROOM_COUNT,
    DungeonGenerationSpec,
    GenerateDungeonAction,
    HomeGenerateDungeonRequest,
    validate_generation_spec,
)
from ai_rpg.services.home_actions import activate_generate_dungeon
from ai_rpg.systems.generate_dungeon_profile_system import (
    _handle_record_dungeon_profile,
    _ProfileResult,
)
from ai_rpg.systems.generate_dungeon_rooms_system import (
    _handle_record_dungeon_rooms,
    _RoomsResult,
)


#######################################################################################################################################
def test_empty_spec_resolves_to_defaults() -> None:
    spec = DungeonGenerationSpec()

    assert spec.resolved_room_count() == DEFAULT_DUNGEON_ROOM_COUNT
    assert spec.resolved_opening_room_count() == DEFAULT_OPENING_ROOM_COUNT
    assert spec.resolved_monsters_per_combat_room() == DEFAULT_MONSTERS_PER_COMBAT_ROOM
    assert validate_generation_spec(spec) is None


def test_spec_overrides_resolve() -> None:
    spec = DungeonGenerationSpec(
        room_count=5, opening_room_count=2, monsters_per_combat_room=3
    )

    assert spec.resolved_room_count() == 5
    assert spec.resolved_opening_room_count() == 2
    assert spec.resolved_monsters_per_combat_room() == 3
    assert validate_generation_spec(spec) is None


#######################################################################################################################################
@pytest.mark.parametrize(
    ("spec", "keyword"),
    [
        (DungeonGenerationSpec(room_count=1), "至少要有 1 个战斗房间"),
        (
            DungeonGenerationSpec(room_count=3, opening_room_count=3),
            "至少要有 1 个战斗房间",
        ),
        (DungeonGenerationSpec(room_count=-1), "不能为负"),
        (DungeonGenerationSpec(monsters_per_combat_room=-2), "不能为负"),
    ],
)
def test_invalid_spec_is_rejected(spec: DungeonGenerationSpec, keyword: str) -> None:
    message = validate_generation_spec(spec)

    assert message is not None
    assert keyword in message


#######################################################################################################################################
def _fake_game() -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.is_player_in_home_stage = True
    world_entity = MagicMock()
    world_entity.name = "世界.副本生成系统"
    world_entity.has.return_value = False
    game.get_group.return_value.entities = {world_entity}
    return game


def _world_entity(game: MagicMock) -> MagicMock:
    return cast(MagicMock, next(iter(game.get_group.return_value.entities)))


def test_activate_without_spec_writes_default_spec() -> None:
    """正式入口（不传 spec）落的是空规格：不覆盖任何默认行为。"""
    game = _fake_game()

    ok, message = activate_generate_dungeon(game)

    assert ok is True
    assert message == ""
    _world_entity(game).replace.assert_called_once_with(
        GenerateDungeonAction,
        "世界.副本生成系统",
        DungeonGenerationSpec(),
    )


def test_activate_with_spec_writes_it_through() -> None:
    game = _fake_game()
    spec = DungeonGenerationSpec(
        room_count=4,
        opening_room_count=1,
        monsters_per_combat_room=2,
        deck_prototype_ids=["proto.summon"] * 5,
    )

    ok, _ = activate_generate_dungeon(game, spec=spec)

    assert ok is True
    _world_entity(game).replace.assert_called_once_with(
        GenerateDungeonAction, "世界.副本生成系统", spec
    )


def test_activate_rejects_invalid_spec_before_pipeline() -> None:
    """矛盾规格在入口即失败，不写动作、不进管道。"""
    game = _fake_game()

    ok, message = activate_generate_dungeon(
        game, spec=DungeonGenerationSpec(room_count=1)
    )

    assert ok is False
    assert "至少要有 1 个战斗房间" in message
    _world_entity(game).replace.assert_not_called()


#######################################################################################################################################
def test_official_api_request_has_no_generation_spec() -> None:
    """正式 API 的请求模型只接受身份字段：没有房间数 / 怪物数 / 牌库规格可传。"""
    fields = set(HomeGenerateDungeonRequest.model_fields)

    assert fields == {"user_name", "game_name"}
    for forbidden in (
        "spec",
        "room_count",
        "opening_room_count",
        "monsters_per_combat_room",
        "deck_prototype_ids",
    ):
        assert forbidden not in fields


#######################################################################################################################################
def test_profile_handler_uses_given_room_count() -> None:
    """房间总数由代码传入，不交给 LLM 自报。"""
    result = _ProfileResult()

    _handle_record_dungeon_profile(result, 4, "副本.试作", "设定")

    assert result.dungeon_room_count == 4


def test_rooms_handler_uses_given_monsters_per_room() -> None:
    result = _RoomsResult()
    rooms: List[Any] = [
        {"room_type": "opening", "room_name": "房间.门", "profile": "门口"},
        {"room_type": "combat", "room_name": "房间.廊", "profile": "长廊"},
        {"room_type": "combat", "room_name": "房间.深处", "profile": "深处"},
    ]

    _handle_record_dungeon_rooms(result, 3, "副本.试作", rooms)

    assert result.rooms is not None
    assert [room.actor_count for room in result.rooms] == [0, 3, 3]


#######################################################################################################################################
def test_assembly_gate_blocks_mismatched_actor_counts() -> None:
    """出厂闸门：怪物数量与房间规格不一致时不落盘（避免产出无怪物的可用副本）。"""
    from ai_rpg.models import (
        DungeonActorDraft,
        DungeonDraft,
        DungeonRoomDraft,
    )
    from ai_rpg.systems.assemble_dungeon_system import AssembleDungeonSystem

    draft = DungeonDraft(
        dungeon_name="副本.试作",
        rooms=[
            DungeonRoomDraft(room_type="opening", room_name="房间.门"),
            DungeonRoomDraft(room_type="combat", room_name="房间.廊", actor_count=1),
        ],
        actors=[],
    )

    mismatch = AssembleDungeonSystem._find_actor_count_mismatch(draft)
    assert "房间.廊" in mismatch
    assert "期望 1 个怪物，实际 0 个" in mismatch

    draft.actors = [
        DungeonActorDraft(room_name="房间.廊", actor_name="怪物.甲"),
    ]
    assert AssembleDungeonSystem._find_actor_count_mismatch(draft) == ""
