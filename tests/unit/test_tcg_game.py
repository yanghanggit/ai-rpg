from typing import Any, List, Optional, cast
import pytest
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.models import PlayerSession
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    ActorType,
    NPCComponent,
    AppearanceComponent,
    CharacterStatsComponent,
    DungeonComponent,
    HandComponent,
    HomeComponent,
    PlayerComponent,
    RoundStatsComponent,
    StageComponent,
    StatusEffectsComponent,
    StatusEffect,
    PhaseType,
    Round,
    CombatRoom,
    Dungeon,
    Actor,
    CharacterSheet,
    CharacterStats,
    Stage,
    StageProfile,
    StageType,
    Blueprint,
    World,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game(
    player_name: str = "p1",
    actor_name: str = "hero",
    blueprint: Optional[Blueprint] = None,
) -> DBGGame:
    """创建带有空世界的 DBGGame 实例（不调用 build_from_blueprint）。"""
    if blueprint is None:
        blueprint = Blueprint(
            name="test",
            player_actor=actor_name,
            campaign_setting="",
            stages=[],
            world_systems=[],
            storage_entity="世界储物箱",
        )
    world = World(
        entity_counter=0,
        home_planning_turn_index=0,
        entities_serialization=[],
        agents_context={},
        dungeon=Dungeon(name="dungeon_alpha", rooms=[], ecology=""),
        blueprint=blueprint,
    )
    session = PlayerSession(name=player_name, actor=actor_name, game="test")
    return DBGGame(name="test", player_session=session, world=world)


def _make_home_stage_entity(game: Any, name: str) -> Entity:
    entity: Entity = cast(Entity, game._create_entity(name))
    entity.add(StageComponent, name, "")
    entity.add(HomeComponent, name)
    return entity


def _make_dungeon_stage_entity(game: Any, name: str) -> Entity:
    entity: Entity = cast(Entity, game._create_entity(name))
    entity.add(StageComponent, name, "")
    entity.add(DungeonComponent, name)
    return entity


def _make_player_actor_entity(
    game: Any, actor_name: str, player_name: str, stage_name: str
) -> Entity:
    entity: Entity = cast(Entity, game._create_entity(actor_name))
    entity.add(ActorComponent, actor_name, "sheet", stage_name)
    entity.add(PlayerComponent, player_name)
    return entity


def _make_actor_entity(game: Any, actor_name: str, stage_name: str = "") -> Entity:
    entity: Entity = cast(Entity, game._create_entity(actor_name))
    entity.add(ActorComponent, actor_name, "sheet", stage_name)
    entity.add(CharacterStatsComponent, actor_name, CharacterStats(hp=20, max_hp=20))
    entity.add(NPCComponent, actor_name)
    entity.add(AppearanceComponent, actor_name, "human body", "")
    return entity


def _make_actor_model(
    name: str,
    actor_type: ActorType = ActorType.NPC,
    hp: int = 30,
    attack: int = 5,
    defense: int = 3,
) -> Actor:
    return Actor(
        name=name,
        character_sheet=CharacterSheet(
            name=f"{name}_sheet",
            type=actor_type,
            profile="",
            base_body="human body",
        ),
        system_message=f"{name} is a character.",
        character_stats=CharacterStats(
            hp=hp, max_hp=hp, attack=attack, defense=defense
        ),
        keywords=["通用型：无特殊约束，自由生成卡牌。"],
    )


def _make_stage_model(
    name: str,
    stage_type: StageType = StageType.HOME,
    actors: Optional[List[Actor]] = None,
) -> Stage:
    return Stage(
        name=name,
        stage_profile=StageProfile(name=f"{name}_profile", type=stage_type, profile=""),
        system_message=f"{name} is a stage.",
        actors=actors or [],
    )


def _make_dungeon_with_enemy(enemy_name: str, stage_name: str) -> Dungeon:
    enemy = _make_actor_model(enemy_name, ActorType.MONSTER)
    stage = _make_stage_model(stage_name, StageType.DUNGEON, actors=[enemy])
    room = CombatRoom(stage=stage)
    return Dungeon(name="test_dungeon", rooms=[room], ecology="")


# ---------------------------------------------------------------------------
# TestCurrentDungeon
# ---------------------------------------------------------------------------


class TestCurrentDungeon:
    def test_returns_world_dungeon(self, sample_game: Any) -> None:
        dungeon = sample_game.current_dungeon
        assert dungeon is sample_game._world.dungeon

    def test_dungeon_name_matches(self) -> None:
        game = _make_game()
        assert game.current_dungeon.name == "dungeon_alpha"


# ---------------------------------------------------------------------------
# TestIsPlayerInStage
# ---------------------------------------------------------------------------


class TestIsPlayerInStage:
    def test_player_in_home_stage_returns_true(self) -> None:
        game = _make_game()
        home = _make_home_stage_entity(game, "home_stage")
        _make_player_actor_entity(game, "hero", "p1", home.name)
        assert game.is_player_in_home_stage is True

    def test_player_in_dungeon_stage_returns_false_for_home(self) -> None:
        game = _make_game()
        home = _make_home_stage_entity(game, "home_stage")
        _make_player_actor_entity(game, "hero", "p1", home.name)
        assert game.is_player_in_dungeon_stage is False

    def test_player_in_dungeon_stage_returns_true(self) -> None:
        game = _make_game()
        dungeon = _make_dungeon_stage_entity(game, "cave")
        _make_player_actor_entity(game, "hero", "p1", dungeon.name)
        assert game.is_player_in_dungeon_stage is True

    def test_player_in_home_stage_returns_false_for_dungeon(self) -> None:
        game = _make_game()
        dungeon = _make_dungeon_stage_entity(game, "cave")
        _make_player_actor_entity(game, "hero", "p1", dungeon.name)
        assert game.is_player_in_home_stage is False

    def test_no_player_entity_raises(self) -> None:
        game = _make_game()
        with pytest.raises(AssertionError):
            _ = game.is_player_in_home_stage


# ---------------------------------------------------------------------------
# TestBuildFromBlueprint
# ---------------------------------------------------------------------------


class TestBuildFromBlueprint:
    def _make_full_blueprint(self) -> Blueprint:
        ally = _make_actor_model("hero", ActorType.NPC)
        home = _make_stage_model("home_stage", StageType.HOME, actors=[ally])
        return Blueprint(
            name="full_test",
            player_actor="hero",
            campaign_setting="",
            stages=[home],
            world_systems=[],
            storage_entity="世界储物箱",
        )

    def _make_game_for_build(self) -> DBGGame:
        bp = self._make_full_blueprint()
        world = World(
            entity_counter=0,
            home_planning_turn_index=0,
            entities_serialization=[],
            agents_context={},
            dungeon=Dungeon(name="", rooms=[], ecology=""),
            blueprint=bp,
        )
        session = PlayerSession(name="p1", actor="hero", game="full_test")
        return DBGGame(name="full_test", player_session=session, world=world)

    def test_actor_entity_created(self) -> None:
        game = self._make_game_for_build()
        game.build_from_blueprint()
        assert game.get_actor_entity("hero") is not None

    def test_stage_entity_created(self) -> None:
        game = self._make_game_for_build()
        game.build_from_blueprint()
        assert game.get_stage_entity("home_stage") is not None

    def test_player_component_assigned(self) -> None:
        game = self._make_game_for_build()
        game.build_from_blueprint()
        hero = game.get_actor_entity("hero")
        assert hero is not None
        assert hero.has(PlayerComponent)

    def test_build_with_existing_entities_raises(self) -> None:
        game = self._make_game_for_build()
        game.build_from_blueprint()
        # entities_serialization is now populated; second call must assert-fail
        with pytest.raises(AssertionError):
            game.build_from_blueprint()


# ---------------------------------------------------------------------------
# TestSetupDungeonEntities
# ---------------------------------------------------------------------------


class TestSetupDungeonEntities:
    def test_setup_creates_actor_entity(self) -> None:
        game = _make_game()
        dungeon = _make_dungeon_with_enemy("goblin", "cave_stage")
        game.setup_dungeon_entities(dungeon)
        assert game.get_actor_entity("goblin") is not None

    def test_setup_creates_stage_entity(self) -> None:
        game = _make_game()
        dungeon = _make_dungeon_with_enemy("goblin", "cave_stage")
        game.setup_dungeon_entities(dungeon)
        assert game.get_stage_entity("cave_stage") is not None

    def test_setup_marks_setup_entities_true(self) -> None:
        game = _make_game()
        dungeon = _make_dungeon_with_enemy("goblin", "cave_stage")
        game.setup_dungeon_entities(dungeon)
        assert dungeon.setup_entities is True

    def test_setup_twice_is_skipped(self) -> None:
        game = _make_game()
        dungeon = _make_dungeon_with_enemy("goblin", "cave_stage")
        game.setup_dungeon_entities(dungeon)
        # Second call should be a no-op (skipped via early return)
        game.setup_dungeon_entities(dungeon)
        # Still only one entity for "goblin" — no assertion error
        assert game.get_actor_entity("goblin") is not None

    def test_npc_actor_type_raises(self) -> None:
        ally = _make_actor_model("hero", ActorType.NPC)
        stage = _make_stage_model("cave_stage", StageType.DUNGEON, actors=[ally])
        room = CombatRoom(stage=stage)
        dungeon = Dungeon(name="d", rooms=[room], ecology="")
        game = _make_game()
        with pytest.raises(AssertionError):
            game.setup_dungeon_entities(dungeon)


# ---------------------------------------------------------------------------
# TestTeardownDungeonEntities
# ---------------------------------------------------------------------------


class TestTeardownDungeonEntities:
    def test_teardown_removes_actor_entity(self) -> None:
        game = _make_game()
        dungeon = _make_dungeon_with_enemy("goblin", "cave_stage")
        game.setup_dungeon_entities(dungeon)
        game.teardown_dungeon_entities(dungeon)
        assert game.get_actor_entity("goblin") is None

    def test_teardown_removes_stage_entity(self) -> None:
        game = _make_game()
        dungeon = _make_dungeon_with_enemy("goblin", "cave_stage")
        game.setup_dungeon_entities(dungeon)
        game.teardown_dungeon_entities(dungeon)
        assert game.get_stage_entity("cave_stage") is None

    def test_teardown_without_setup_is_safe(self) -> None:
        game = _make_game()
        dungeon = _make_dungeon_with_enemy("goblin", "cave_stage")
        # Nothing was set up; teardown should not raise
        game.teardown_dungeon_entities(dungeon)


# ---------------------------------------------------------------------------
# TestClearRoundState
# ---------------------------------------------------------------------------


class TestClearRoundState:
    def test_hand_component_removed(self) -> None:
        from src.ai_rpg.models import DrawPileComponent

        game = _make_game()
        actor = _make_actor_entity(game, "fighter")
        actor.add(DrawPileComponent, "fighter", [])
        actor.add(HandComponent, "fighter", [], 1)
        game.clear_round_state()
        assert not actor.has(HandComponent)

    def test_round_stats_component_removed(self) -> None:
        game = _make_game()
        actor = _make_actor_entity(game, "fighter")
        actor.add(RoundStatsComponent, "fighter", 3)
        game.clear_round_state()
        assert not actor.has(RoundStatsComponent)

    def test_clear_with_no_components_is_safe(self) -> None:
        game = _make_game()
        _make_actor_entity(game, "fighter")
        # Should not raise even without HandComponent or RoundStatsComponent
        game.clear_round_state()

    def test_multiple_actors_all_cleared(self) -> None:
        from src.ai_rpg.models import DrawPileComponent

        game = _make_game()
        for name in ("a1", "a2", "a3"):
            actor = _make_actor_entity(game, name)
            actor.add(DrawPileComponent, name, [])
            actor.add(HandComponent, name, [], 1)
            actor.add(RoundStatsComponent, name, 2)
        game.clear_round_state()
        for name in ("a1", "a2", "a3"):
            entity = game.get_actor_entity(name)
            assert entity is not None
            assert not entity.has(HandComponent)
            assert not entity.has(RoundStatsComponent)


# ---------------------------------------------------------------------------
# TestClearStatusEffects
# ---------------------------------------------------------------------------


class TestClearStatusEffects:
    def test_status_effects_removed(self) -> None:
        game = _make_game()
        actor = _make_actor_entity(game, "witch")
        effect = StatusEffect(
            name="burn",
            phase=PhaseType.ARBITRATION,
            description="burns",
            duration=2,
        )
        actor.add(StatusEffectsComponent, "witch", [effect])
        game.clear_status_effects()
        assert not actor.has(StatusEffectsComponent)

    def test_no_actors_with_status_effects_is_safe(self) -> None:
        game = _make_game()
        _make_actor_entity(game, "guard")
        game.clear_status_effects()


# ---------------------------------------------------------------------------
# TestComputeCharacterStats
# ---------------------------------------------------------------------------


class TestComputeCharacterStats:
    def test_base_stats_returned(self) -> None:
        game = _make_game()
        actor = _make_actor_entity(game, "knight")
        stats = game.compute_character_stats(actor)
        assert stats.max_hp == 20
        assert stats.attack == 5
        assert stats.defense == 3

    def test_missing_actor_component_raises(self) -> None:
        game = _make_game()
        entity = game._create_entity("ghost")
        entity.add(CharacterStatsComponent, "ghost", CharacterStats())
        with pytest.raises(AssertionError):
            game.compute_character_stats(entity)

    def test_missing_stats_component_raises(self) -> None:
        game = _make_game()
        entity = game._create_entity("ghost")
        entity.add(ActorComponent, "ghost", "sheet", "")
        with pytest.raises(AssertionError):
            game.compute_character_stats(entity)

    def test_no_equipment_uses_base_stats(self) -> None:
        game = _make_game()
        actor = _make_actor_entity(game, "rogue")
        stats = game.compute_character_stats(actor)
        # Without equipment bonuses, stats should equal base
        assert stats.attack == 5
        assert stats.defense == 3


# ---------------------------------------------------------------------------
# TestSetCharacterHp
# ---------------------------------------------------------------------------


class TestSetCharacterHp:
    def test_set_normal_hp(self) -> None:
        game = _make_game()
        actor = _make_actor_entity(game, "warrior")
        game.set_character_hp(actor, 10)
        result = game.compute_character_stats(actor)
        assert result.hp == 10

    def test_clamp_negative_hp_to_zero(self) -> None:
        game = _make_game()
        actor = _make_actor_entity(game, "warrior")
        game.set_character_hp(actor, -5)
        result = game.compute_character_stats(actor)
        assert result.hp == 0

    def test_clamp_exceeding_max_hp(self) -> None:
        game = _make_game()
        actor = _make_actor_entity(game, "warrior")
        game.set_character_hp(actor, 9999)
        result = game.compute_character_stats(actor)
        assert result.hp == 20  # max_hp is 20

    def test_set_hp_to_max(self) -> None:
        game = _make_game()
        actor = _make_actor_entity(game, "warrior")
        game.set_character_hp(actor, 20)
        result = game.compute_character_stats(actor)
        assert result.hp == 20


# ---------------------------------------------------------------------------
# TestGetCurrentTurnActor
# ---------------------------------------------------------------------------


class TestGetCurrentTurnActor:
    def test_no_snapshots_returns_none(self) -> None:
        game = _make_game()
        round_ = Round()
        assert game.get_current_turn_actor(round_) is None

    def test_actor_with_energy_returned(self) -> None:
        game = _make_game()
        actor = _make_actor_entity(game, "mage")
        actor.add(RoundStatsComponent, "mage", 2)
        round_ = Round(actor_order_snapshots=[["mage"]])
        result = game.get_current_turn_actor(round_)
        assert result == "mage"

    def test_all_zero_energy_returns_none(self) -> None:
        game = _make_game()
        actor = _make_actor_entity(game, "mage")
        actor.add(RoundStatsComponent, "mage", 0)
        round_ = Round(actor_order_snapshots=[["mage"]])
        result = game.get_current_turn_actor(round_)
        assert result is None

    def test_first_nonzero_energy_actor_returned(self) -> None:
        game = _make_game()
        a1 = _make_actor_entity(game, "a1")
        a2 = _make_actor_entity(game, "a2")
        a1.add(RoundStatsComponent, "a1", 0)
        a2.add(RoundStatsComponent, "a2", 1)
        round_ = Round(actor_order_snapshots=[["a1", "a2"]])
        result = game.get_current_turn_actor(round_)
        assert result == "a2"
