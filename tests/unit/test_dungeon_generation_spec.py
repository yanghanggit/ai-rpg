"""副本生成显式规格（调测用）单测：结构校验、入口接线、以及「正式 API 无法作弊」。

规格只经由 `GenerateDungeonAction.spec` 传递；本文件验证三件事：
- 规格自洽性校验与默认值解析；
- 开发入口 `activate_generate_dungeon(spec=...)` 的写入与拒绝；
- 正式 API 的请求模型里**没有**任何规格字段（线上无法传递）。
"""

from typing import Any, List, Literal, Tuple, cast
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
    validate_room_layout,
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
            DungeonRoomDraft(
                room_type="opening", room_name="房间.门", profile="门口景象"
            ),
            DungeonRoomDraft(
                room_type="combat",
                room_name="房间.廊",
                profile="长廊景象",
                actor_count=1,
            ),
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


#######################################################################################################################################
def _room(room_type: Literal["opening", "combat"], name: str) -> Any:
    from ai_rpg.models import DungeonRoomDraft

    return DungeonRoomDraft(room_type=room_type, room_name=name)


def test_room_layout_accepts_opening_prefix() -> None:
    """多开场房是合法布局：前 N 间开场、其余战斗。"""
    rooms = [
        _room("opening", "房间.门"),
        _room("opening", "房间.廊"),
        _room("combat", "房间.深处"),
    ]

    assert (
        validate_room_layout(rooms, expected_room_count=3, opening_room_count=2) == ""
    )


def test_room_layout_rejects_wrong_count() -> None:
    rooms = [_room("opening", "房间.门")]

    message = validate_room_layout(rooms, expected_room_count=2, opening_room_count=1)

    assert "房间数量不符" in message


def test_room_layout_rejects_combat_before_opening_prefix() -> None:
    """顺序不可交换：第 2 间若还是 combat，而规格要求 2 间开场，就必须拒绝。"""
    rooms = [_room("opening", "房间.门"), _room("combat", "房间.廊")]

    message = validate_room_layout(rooms, expected_room_count=2, opening_room_count=2)

    assert "第 2 个房间" in message
    assert "'opening'" in message


def test_room_layout_rejects_trailing_opening() -> None:
    rooms = [_room("opening", "房间.门"), _room("opening", "房间.廊")]

    message = validate_room_layout(rooms, expected_room_count=2, opening_room_count=1)

    assert "第 2 个房间" in message
    assert "'combat'" in message


#######################################################################################################################################
async def _run_assembly_with(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    draft: Any,
) -> Tuple[bool, MagicMock]:
    """跑一次组装步骤，返回 (是否落盘, game)。落盘目录整体指向 tmp_path。"""
    from ai_rpg.systems import assemble_dungeon_system as assembly_module

    monkeypatch.setattr(assembly_module, "DUNGEONS_DIR", tmp_path / "dungeons")
    monkeypatch.setattr(assembly_module, "DUNGEONS_DRAFTS_DIR", tmp_path / "drafts")
    (tmp_path / "dungeons").mkdir()
    (tmp_path / "drafts").mkdir()

    # 组装步骤只用到世界蓝图的两段文案与中间数据；不用 spec 约束，避免私有属性被拦
    game = MagicMock()
    game._dungeon_draft = draft
    game._world = MagicMock()
    game._world.blueprint.campaign_setting = "设定"
    game._world.blueprint.system_rules = "规则"
    system = assembly_module.AssembleDungeonSystem(game)

    await system._run()

    written = any((tmp_path / "dungeons").iterdir())
    return written, game


async def test_assembly_gate_skips_write_on_mismatch(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """上游失败（怪物数不符）时不落盘：不会产出「无怪物的可用副本」。"""
    from ai_rpg.models import DungeonDraft, DungeonRoomDraft

    draft = DungeonDraft(
        dungeon_name="副本.试作",
        profile="设定",
        rooms=[
            DungeonRoomDraft(
                room_type="opening", room_name="房间.门", profile="门口景象"
            ),
            DungeonRoomDraft(
                room_type="combat",
                room_name="房间.廊",
                profile="长廊景象",
                actor_count=1,
            ),
        ],
        actors=[],
    )

    written, _ = await _run_assembly_with(tmp_path, monkeypatch, draft)

    assert written is False
    assert list((tmp_path / "drafts").iterdir()) == []


async def test_assembly_writes_when_counts_match(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """闸门不能误伤正常产物：数量一致时照常落盘。"""
    from ai_rpg.models import DungeonActorDraft, DungeonDraft, DungeonRoomDraft

    draft = DungeonDraft(
        dungeon_name="副本.试作",
        profile="设定",
        rooms=[
            DungeonRoomDraft(
                room_type="opening", room_name="房间.门", profile="门口景象"
            ),
            DungeonRoomDraft(
                room_type="combat",
                room_name="房间.廊",
                profile="长廊景象",
                actor_count=1,
            ),
        ],
        actors=[
            DungeonActorDraft(
                room_name="房间.廊",
                actor_name="怪物.甲",
                profile="扮演设定",
                base_body="外观",
            )
        ],
    )

    written, _ = await _run_assembly_with(tmp_path, monkeypatch, draft)

    assert written is True
    assert (tmp_path / "dungeons" / "副本.试作.json").exists()
