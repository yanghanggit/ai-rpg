"""
Unit tests for src/ai_rpg/services/dungeon_advance_action.py
and src/ai_rpg/services/dungeon_exit_action.py

覆盖本次收紧后的状态守卫：
  - current_room_index 无效（-1 尚未进入 / 越界）时拒绝推进与退出
    （回归：防止 `dungeon.rooms[current_room_index]` 在 -1 时回绕到最后一个房间）
  - 开场房间（OpeningRoom）未初始化时拒绝推进与退出（与 CombatRoom 对称收紧）
  - 开场房间已初始化时，推进 / 退出正常执行
"""

from typing import Any, List

from ai_rpg.entitas.entity import Entity
from ai_rpg.models import (
    ActorComponent,
    CharacterStats,
    CharacterStatsComponent,
    DungeonComponent,
    HomeComponent,
    PartyMemberComponent,
    Stage,
    StageComponent,
    StageType,
)
from ai_rpg.models.dungeon import (
    AnyDungeonRoom,
    Dungeon,
    OpeningRoom,
)
from ai_rpg.services.dungeon_advance_action import advance_dungeon
from ai_rpg.services.dungeon_exit_action import exit_dungeon

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stage_model(name: str) -> Stage:
    """构造一个合法的 Stage 模型（副本房间场景）。"""
    return Stage(
        name=name,
        type=StageType.DUNGEON,
        profile="profile",
        system_message="system",
        actors=[],
    )


def _make_dungeon(rooms: List[AnyDungeonRoom], index: int) -> Dungeon:
    """构造一个副本，并显式设置 current_room_index（可为 -1 / 越界）。"""
    dungeon = Dungeon(name="test_dungeon", rooms=rooms, profile="profile")
    dungeon.current_room_index = index
    return dungeon


def _make_stage_entity(game: Any, name: str) -> Entity:
    """创建带 StageComponent + DungeonComponent 的场景实体。"""
    entity: Entity = game._create_entity(name)
    entity.add(StageComponent, name)
    entity.add(DungeonComponent, name)
    return entity


def _make_home_entity(game: Any, name: str) -> Entity:
    """创建带 StageComponent + HomeComponent 的家园场景实体。"""
    entity: Entity = game._create_entity(name)
    entity.add(StageComponent, name)
    entity.add(HomeComponent, name)
    return entity


def _make_party_member(game: Any, name: str, stage_name: str) -> Entity:
    """创建带 ActorComponent + CharacterStatsComponent + PartyMemberComponent 的队伍成员。"""
    entity: Entity = game._create_entity(name)
    entity.add(ActorComponent, name, stage_name)
    entity.add(
        CharacterStatsComponent,
        name,
        CharacterStats(hp=3, max_hp=10, attack=1, defense=1),
    )
    entity.add(PartyMemberComponent, name)
    return entity


# ---------------------------------------------------------------------------
# advance_dungeon
# ---------------------------------------------------------------------------


class TestAdvanceDungeonGuards:
    async def test_rejects_when_current_room_index_is_negative(
        self, sample_game: Any
    ) -> None:
        """current_room_index == -1（尚未进入）时拒绝推进，不回绕到 rooms[-1]。"""
        dungeon = _make_dungeon([OpeningRoom(stage=_make_stage_model("room0"))], -1)
        sample_game._world.dungeon = dungeon

        ok, msg = await advance_dungeon(sample_game, dungeon)

        assert ok is False
        assert "尚未进入" in msg
        # 未推进：索引保持 -1
        assert dungeon.current_room_index == -1

    async def test_rejects_when_current_room_index_is_out_of_range(
        self, sample_game: Any
    ) -> None:
        """current_room_index 越界（脏存档）时拒绝推进，而不是 IndexError。"""
        dungeon = _make_dungeon([OpeningRoom(stage=_make_stage_model("room0"))], 5)
        sample_game._world.dungeon = dungeon

        ok, msg = await advance_dungeon(sample_game, dungeon)

        assert ok is False
        assert "尚未进入" in msg

    async def test_rejects_uninitialized_opening_room(self, sample_game: Any) -> None:
        """开场房间未初始化时拒绝推进（与 CombatRoom 对称收紧）。"""
        room0 = OpeningRoom(stage=_make_stage_model("room0"))  # initialized=False
        room1 = OpeningRoom(stage=_make_stage_model("room1"))
        dungeon = _make_dungeon([room0, room1], 0)
        sample_game._world.dungeon = dungeon

        _make_stage_entity(sample_game, "room1")  # 下一关场景实体（校验通过）
        _make_party_member(sample_game, "hero", "room0")

        ok, msg = await advance_dungeon(sample_game, dungeon)

        assert ok is False
        assert "尚未初始化" in msg
        assert dungeon.current_room_index == 0

    async def test_advances_initialized_opening_room(self, sample_game: Any) -> None:
        """开场房间已初始化时正常推进到下一关。"""
        room0 = OpeningRoom(stage=_make_stage_model("room0"))
        room0.initialized = True
        room1 = OpeningRoom(stage=_make_stage_model("room1"))
        dungeon = _make_dungeon([room0, room1], 0)
        sample_game._world.dungeon = dungeon

        _make_stage_entity(
            sample_game, "room0"
        )  # 当前场景实体（stage_transition 需要）
        _make_stage_entity(sample_game, "room1")  # 下一关场景实体
        member = _make_party_member(sample_game, "hero", "room0")

        ok, msg = await advance_dungeon(sample_game, dungeon)

        assert ok is True
        assert dungeon.current_room_index == 1
        # 队伍成员已被传送到下一关场景
        actor_comp = member.get(ActorComponent)
        assert actor_comp is not None
        assert actor_comp.current_stage == "room1"


# ---------------------------------------------------------------------------
# exit_dungeon
# ---------------------------------------------------------------------------


class TestExitDungeonGuards:
    def test_rejects_when_current_room_index_is_negative(
        self, sample_game: Any
    ) -> None:
        """current_room_index == -1（尚未进入）时拒绝退出，不回绕到 rooms[-1]。"""
        dungeon = _make_dungeon([OpeningRoom(stage=_make_stage_model("room0"))], -1)
        sample_game._world.dungeon = dungeon

        ok, msg = exit_dungeon(sample_game, dungeon)

        assert ok is False
        assert "尚未进入" in msg

    def test_rejects_when_current_room_index_is_out_of_range(
        self, sample_game: Any
    ) -> None:
        """current_room_index 越界（脏存档）时拒绝退出，而不是 IndexError。"""
        dungeon = _make_dungeon([OpeningRoom(stage=_make_stage_model("room0"))], 5)
        sample_game._world.dungeon = dungeon

        ok, msg = exit_dungeon(sample_game, dungeon)

        assert ok is False
        assert "尚未进入" in msg

    def test_rejects_uninitialized_opening_room(self, sample_game: Any) -> None:
        """开场房间未初始化时拒绝退出（与 CombatRoom 对称收紧）。"""
        room0 = OpeningRoom(stage=_make_stage_model("room0"))  # initialized=False
        dungeon = _make_dungeon([room0], 0)
        sample_game._world.dungeon = dungeon

        ok, msg = exit_dungeon(sample_game, dungeon)

        assert ok is False
        assert "尚未初始化" in msg

    def test_exits_initialized_opening_room(self, sample_game: Any) -> None:
        """开场房间已初始化时正常退出并恢复队伍成员到家。"""
        room0 = OpeningRoom(stage=_make_stage_model("room0"))
        room0.initialized = True
        dungeon = _make_dungeon([room0], 0)
        sample_game._world.dungeon = dungeon

        _make_stage_entity(
            sample_game, "room0"
        )  # 当前场景实体（stage_transition 需要）
        _make_home_entity(sample_game, "home")  # 家园目标场景
        member = _make_party_member(sample_game, "hero", "room0")

        ok, msg = exit_dungeon(sample_game, dungeon)

        assert ok is True
        # 队伍标记被移除
        assert not member.has(PartyMemberComponent)
        # 成员已被传送回家园
        actor_comp = member.get(ActorComponent)
        assert actor_comp is not None
        assert actor_comp.current_stage == "home"
