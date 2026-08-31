"""针对 `resolve_targets`（ALL/SPREAD 阵营锚点展开逻辑）的单元测试。"""

from typing import Any, cast

from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_combat_processor import resolve_targets
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    Blueprint,
    DeathComponent,
    Dungeon,
    DungeonComponent,
    MonsterComponent,
    PartyMemberComponent,
    PlayerSession,
    StageComponent,
    TargetType,
    WorldState,
)


def _make_game(player_name: str = "player", actor_name: str = "hero") -> DBGGame:
    blueprint = Blueprint(
        name="test",
        player_actor=actor_name,
        campaign_setting="",
        system_rules="",
        knowledge_base={},
        stages=[],
        world_entities=[],
        storage_entity="世界储物箱",
    )
    world = WorldState(
        entity_counter=0,
        entities=[],
        agent_memories={},
        dungeon=Dungeon(name="dungeon_alpha", rooms=[], profile=""),
        blueprint=blueprint,
    )
    session = PlayerSession(name=player_name, actor=actor_name, game="test")
    return DBGGame(name="test", player_session=session, world=world)


def _make_stage(game: Any, name: str) -> Entity:
    entity: Entity = cast(Entity, game._create_entity(name))
    entity.add(StageComponent, name)
    entity.add(DungeonComponent, name)
    return entity


def _make_ally(game: Any, name: str, stage_name: str, dead: bool = False) -> Entity:
    entity: Entity = cast(Entity, game._create_entity(name))
    entity.add(ActorComponent, name, stage_name)
    entity.add(PartyMemberComponent, name)
    if dead:
        entity.add(DeathComponent, name)
    return entity


def _make_monster(game: Any, name: str, stage_name: str, dead: bool = False) -> Entity:
    entity: Entity = cast(Entity, game._create_entity(name))
    entity.add(ActorComponent, name, stage_name)
    entity.add(MonsterComponent, name)
    if dead:
        entity.add(DeathComponent, name)
    return entity


class TestResolveTargetsSingle:
    def test_single_rejects_missing_anchor(self) -> None:
        game = _make_game()
        stage = _make_stage(game, "stage1")
        hero = _make_ally(game, "hero", "stage1")
        _make_monster(game, "怪物A", "stage1")
        del stage

        targets, err = resolve_targets(TargetType.SINGLE, 1, hero, [], game)
        assert targets == []
        assert "目标数量必须为 1" in err

    def test_single_rejects_multiple_anchors(self) -> None:
        game = _make_game()
        _make_stage(game, "stage1")
        hero = _make_ally(game, "hero", "stage1")
        _make_monster(game, "怪物A", "stage1")

        targets, err = resolve_targets(
            TargetType.SINGLE, 1, hero, ["怪物A", "怪物B"], game
        )
        assert targets == []
        assert "目标数量必须为 1" in err

    def test_single_target_must_be_alive_in_stage(self) -> None:
        game = _make_game()
        _make_stage(game, "stage1")
        hero = _make_ally(game, "hero", "stage1")
        _make_monster(game, "怪物A", "stage1", dead=True)

        targets, err = resolve_targets(TargetType.SINGLE, 1, hero, ["怪物A"], game)
        assert targets == []
        assert "不在当前场景存活角色列表中" in err

    def test_single_resolves_to_passed_target(self) -> None:
        game = _make_game()
        _make_stage(game, "stage1")
        hero = _make_ally(game, "hero", "stage1")
        _make_monster(game, "怪物A", "stage1")

        targets, err = resolve_targets(TargetType.SINGLE, 1, hero, ["怪物A"], game)
        assert err == ""
        assert targets == ["怪物A"]


class TestResolveTargetsAll:
    def test_all_anchor_enemy_expands_to_all_alive_enemies(self) -> None:
        game = _make_game()
        _make_stage(game, "stage1")
        hero = _make_ally(game, "hero", "stage1")
        _make_monster(game, "怪物A", "stage1")
        _make_monster(game, "怪物B", "stage1")
        _make_monster(game, "怪物C", "stage1", dead=True)

        targets, err = resolve_targets(TargetType.ALL, 1, hero, ["怪物A"], game)
        assert err == ""
        assert set(targets) == {"怪物A", "怪物B"}

    def test_all_anchor_self_expands_to_all_allies_including_actor(self) -> None:
        game = _make_game()
        _make_stage(game, "stage1")
        hero = _make_ally(game, "hero", "stage1")
        _make_ally(game, "队友A", "stage1")
        _make_monster(game, "怪物A", "stage1")

        targets, err = resolve_targets(TargetType.ALL, 1, hero, ["hero"], game)
        assert err == ""
        # 阵营展开不排除行动者自己
        assert set(targets) == {"hero", "队友A"}

    def test_all_rejects_dead_or_nonexistent_anchor(self) -> None:
        game = _make_game()
        _make_stage(game, "stage1")
        hero = _make_ally(game, "hero", "stage1")
        _make_monster(game, "怪物A", "stage1", dead=True)

        targets, err = resolve_targets(TargetType.ALL, 1, hero, ["怪物A"], game)
        assert targets == []
        assert "不在当前场景存活角色列表中" in err

        targets2, err2 = resolve_targets(TargetType.ALL, 1, hero, ["不存在的人"], game)
        assert targets2 == []
        assert "不在当前场景存活角色列表中" in err2

    def test_all_rejects_anchor_without_camp_component(self) -> None:
        game = _make_game()
        _make_stage(game, "stage1")
        hero = _make_ally(game, "hero", "stage1")
        neutral = game._create_entity("中立者")
        neutral.add(ActorComponent, "中立者", "stage1")

        targets, err = resolve_targets(TargetType.ALL, 1, hero, ["中立者"], game)
        assert targets == []
        assert "不属于任何可识别阵营" in err


class TestResolveTargetsSpread:
    def test_spread_anchor_enemy_hits_len_equals_hit_count(self) -> None:
        game = _make_game()
        _make_stage(game, "stage1")
        hero = _make_ally(game, "hero", "stage1")
        _make_monster(game, "怪物A", "stage1")
        _make_monster(game, "怪物B", "stage1")

        targets, err = resolve_targets(TargetType.SPREAD, 5, hero, ["怪物A"], game)
        assert err == ""
        assert len(targets) == 5
        assert set(targets) <= {"怪物A", "怪物B"}
        # hit_count(5) > 敌方数量(2)，保证每人至少命中一次
        assert set(targets) == {"怪物A", "怪物B"}

    def test_spread_anchor_self_can_include_actor(self) -> None:
        game = _make_game()
        _make_stage(game, "stage1")
        hero = _make_ally(game, "hero", "stage1")
        _make_ally(game, "队友A", "stage1")

        targets, err = resolve_targets(TargetType.SPREAD, 4, hero, ["hero"], game)
        assert err == ""
        assert len(targets) == 4
        assert set(targets) <= {"hero", "队友A"}


class TestResolveTargetsSelf:
    def test_self_ignores_anchor_and_returns_actor(self) -> None:
        game = _make_game()
        _make_stage(game, "stage1")
        hero = _make_ally(game, "hero", "stage1")
        _make_monster(game, "怪物A", "stage1")

        targets, err = resolve_targets(
            TargetType.SINGLE, 1, hero, [], game, self_target=True
        )
        assert err == ""
        assert targets == ["hero"]
