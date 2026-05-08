"""
Unit tests for src/ai_rpg/systems/home_actor_plan_system.py

覆盖范围：
  - filter（仅 NPC 实体通过，PlayerComponent 实体被排除）
  - _is_player_active（无参，查询游戏状态）
  - _get_other_actors_appearances
  - _get_available_home_stages
  - _inject_npc_standby_context
  - _execute_actor_actions
  - react() 集成路径（player-active / player-passive+NPC）

玩家上下文注入相关逻辑（_build_player_action_response / _inject_player_scene_context）
已迁移至 HomePlayerContextSystem，在本文件中通过 _make_player_system 测试。
"""

import json
from typing import Any, Optional, cast
from unittest.mock import AsyncMock, patch
from src.ai_rpg.deepseek import DeepSeekClient
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.player_session import PlayerSession
from src.ai_rpg.game.tcg_game import TCGGame
from src.ai_rpg.models import (
    NPCComponent,
    AnnounceAction,
    AppearanceComponent,
    EquipItemAction,
    HomeComponent,
    PlayerComponent,
    PlayerOnlyStageComponent,
    QueryAction,
    SpeakAction,
    StageComponent,
    StageDescriptionComponent,
    TransStageAction,
    WhisperAction,
    PlanAction,
    ActorComponent,
)
from src.ai_rpg.models.dungeon import Dungeon
from src.ai_rpg.models.messages import AIMessage
from src.ai_rpg.models.world import Blueprint, World
from src.ai_rpg.systems.home_npc_plan_system import HomeNpcPlanSystem
from src.ai_rpg.systems.home_player_context_system import HomePlayerContextSystem
from src.ai_rpg.systems.home_planning_utils import is_player_active


# ---------------------------------------------------------------------------
# Fake stub for DeepSeekClient
# ---------------------------------------------------------------------------


class _FakeClient:
    """Minimal stub mimicking DeepSeekClient for _execute_actor_actions tests."""

    def __init__(self, name: str, response_json: dict[str, Any]) -> None:
        self.name = name
        json_str = json.dumps(response_json)
        self.response_content: str = json_str
        self.compressed_prompt: str = "compressed_prompt"
        self.prompt: str = "full_prompt"
        self.response_ai_message: Optional[AIMessage] = AIMessage(content=json_str)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game() -> TCGGame:
    blueprint = Blueprint(
        name="test",
        player_actor="hero",
        player_only_stage="private_stage",
        campaign_setting="",
        stages=[],
        world_systems=[],
    )
    world = World(
        entity_counter=0,
        home_planning_turn_index=0,
        entities_serialization=[],
        agents_context={},
        dungeon=Dungeon(name="", rooms=[], ecology=""),
        blueprint=blueprint,
    )
    session = PlayerSession(name="p1", actor="hero", game="test")
    return TCGGame(name="test", player_session=session, world=world)


def _make_home_stage(game: Any, name: str, narrative: str = "a quiet hall") -> Entity:
    entity: Entity = game._create_entity(name)
    entity.add(StageComponent, name, "")
    entity.add(HomeComponent, name)
    entity.add(StageDescriptionComponent, name, narrative)
    return entity


def _make_actor(game: Any, name: str, stage_name: str) -> Entity:
    entity: Entity = game._create_entity(name)
    entity.add(ActorComponent, name, "sheet", stage_name)
    entity.add(NPCComponent, name)
    entity.add(AppearanceComponent, name, "human body", f"{name} appearance")
    return entity


def _make_player_actor(game: Any, name: str, stage_name: str) -> Entity:
    entity: Entity = _make_actor(game, name, stage_name)
    entity.add(PlayerComponent, "p1")
    return entity


def _make_system(
    game: TCGGame, use_compressed_prompt: bool = True
) -> HomeNpcPlanSystem:
    return HomeNpcPlanSystem(game, use_compressed_prompt=use_compressed_prompt)


def _make_player_system(
    game: TCGGame, use_compressed_prompt: bool = True
) -> HomePlayerContextSystem:
    return HomePlayerContextSystem(game, use_compressed_prompt=use_compressed_prompt)


def _action_plan_json(**overrides: Any) -> dict[str, Any]:
    """Build a minimal valid ActionPlanResponse JSON dict."""
    base: dict[str, Any] = {
        "mind": "",
        "query": "",
        "inspect_self": False,
        "equip_weapon": None,
        "equip_armor": None,
        "equip_accessory": None,
        "speak": {},
        "whisper": {},
        "announce": "",
        "trans_stage": "",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TestFilter
# ---------------------------------------------------------------------------


class TestFilter:
    def test_entity_with_plan_and_actor_passes(self) -> None:
        game = _make_game()
        system = _make_system(game)
        entity = _make_actor(game, "knight", "home")
        entity.add(PlanAction, "knight")
        assert system.filter(entity) is True

    def test_entity_with_plan_no_actor_fails(self) -> None:
        game = _make_game()
        system = _make_system(game)
        entity: Entity = game._create_entity("ghost")
        entity.add(PlanAction, "ghost")
        assert system.filter(entity) is False

    def test_player_entity_filtered_out(self) -> None:
        # PlayerComponent entities are handled by HomePlayerContextSystem, not here
        game = _make_game()
        system = _make_system(game)
        player = _make_player_actor(game, "hero", "home")
        player.add(PlanAction, "hero")
        assert system.filter(player) is False


# ---------------------------------------------------------------------------
# TestIsPlayerActive
# ---------------------------------------------------------------------------


class TestIsPlayerActive:
    def test_no_player_entity_returns_false(self) -> None:
        game = _make_game()
        assert is_player_active(game) is False

    def test_player_without_active_action_returns_false(self) -> None:
        game = _make_game()
        _make_player_actor(game, "hero", "home")
        assert is_player_active(game) is False

    def test_player_with_speak_action_returns_true(self) -> None:
        game = _make_game()
        player = _make_player_actor(game, "hero", "home")
        player.add(SpeakAction, "hero", {"npc": "hello"})
        assert is_player_active(game) is True

    def test_player_with_trans_stage_action_returns_true(self) -> None:
        game = _make_game()
        player = _make_player_actor(game, "hero", "home")
        player.add(TransStageAction, "hero", "library")
        assert is_player_active(game) is True


# ---------------------------------------------------------------------------
# TestBuildPlayerActionResponse
# ---------------------------------------------------------------------------


class TestBuildPlayerActionResponse:
    def test_no_actions_uses_passive_mind(self) -> None:
        game = _make_game()
        system = _make_player_system(game)
        player = _make_player_actor(game, "hero", "home")
        result = system._build_player_action_response(player, "passive thought")
        assert result.mind == "passive thought"
        assert result.speak == {}
        assert result.whisper == {}
        assert result.announce == ""
        assert result.trans_stage == ""

    def test_speak_action_populates_speak(self) -> None:
        game = _make_game()
        system = _make_player_system(game)
        player = _make_player_actor(game, "hero", "home")
        player.add(SpeakAction, "hero", {"npc": "greetings"})
        result = system._build_player_action_response(player, "ignored")
        assert result.speak == {"npc": "greetings"}

    def test_whisper_action_populates_whisper(self) -> None:
        game = _make_game()
        system = _make_player_system(game)
        player = _make_player_actor(game, "hero", "home")
        player.add(WhisperAction, "hero", {"npc": "secret"})
        result = system._build_player_action_response(player, "ignored")
        assert result.whisper == {"npc": "secret"}

    def test_announce_action_populates_announce(self) -> None:
        game = _make_game()
        system = _make_player_system(game)
        player = _make_player_actor(game, "hero", "home")
        player.add(AnnounceAction, "hero", "public announcement")
        result = system._build_player_action_response(player, "ignored")
        assert result.announce == "public announcement"

    def test_trans_stage_action_populates_trans_stage(self) -> None:
        game = _make_game()
        system = _make_player_system(game)
        player = _make_player_actor(game, "hero", "home")
        player.add(TransStageAction, "hero", "library")
        result = system._build_player_action_response(player, "ignored")
        assert result.trans_stage == "library"

    def test_equip_item_action_populates_equip_fields(self) -> None:
        game = _make_game()
        system = _make_player_system(game)
        player = _make_player_actor(game, "hero", "home")
        player.add(EquipItemAction, "hero", "iron sword", None, "ring of power")
        result = system._build_player_action_response(player, "ignored")
        assert result.equip_weapon == "iron sword"
        assert result.equip_armor is None
        assert result.equip_accessory == "ring of power"

    def test_active_action_sets_mind_to_empty(self) -> None:
        game = _make_game()
        system = _make_player_system(game)
        player = _make_player_actor(game, "hero", "home")
        player.add(SpeakAction, "hero", {"npc": "hi"})
        result = system._build_player_action_response(player, "should be ignored")
        assert result.mind == ""


# ---------------------------------------------------------------------------
# TestGetOtherActorsAppearances
# ---------------------------------------------------------------------------


class TestGetOtherActorsAppearances:
    def test_only_self_returns_empty_dict(self) -> None:
        game = _make_game()
        system = _make_system(game)
        stage = _make_home_stage(game, "home")
        actor = _make_actor(game, "hero", "home")
        result = system._get_other_actors_appearances(actor, stage)
        assert result == {}

    def test_one_other_actor_in_stage_is_returned(self) -> None:
        game = _make_game()
        system = _make_system(game)
        stage = _make_home_stage(game, "home")
        hero = _make_actor(game, "hero", "home")
        _make_actor(game, "npc", "home")
        result = system._get_other_actors_appearances(hero, stage)
        assert "npc" in result
        assert "hero" not in result

    def test_two_other_actors_both_returned(self) -> None:
        game = _make_game()
        system = _make_system(game)
        stage = _make_home_stage(game, "home")
        hero = _make_actor(game, "hero", "home")
        _make_actor(game, "npc1", "home")
        _make_actor(game, "npc2", "home")
        result = system._get_other_actors_appearances(hero, stage)
        assert "npc1" in result
        assert "npc2" in result
        assert "hero" not in result


# ---------------------------------------------------------------------------
# TestGetAvailableHomeStages
# ---------------------------------------------------------------------------


class TestGetAvailableHomeStages:
    def test_no_other_home_stages_returns_empty(self) -> None:
        game = _make_game()
        system = _make_system(game)
        stage = _make_home_stage(game, "only_home")
        actor = _make_actor(game, "hero", "only_home")
        result = system._get_available_home_stages(actor, stage)
        assert result == set()

    def test_npc_can_go_to_public_home_stage(self) -> None:
        game = _make_game()
        system = _make_system(game)
        current = _make_home_stage(game, "hall")
        library = _make_home_stage(game, "library")
        npc = _make_actor(game, "npc", "hall")
        result = system._get_available_home_stages(npc, current)
        assert library in result

    def test_npc_cannot_go_to_player_only_stage(self) -> None:
        game = _make_game()
        system = _make_system(game)
        current = _make_home_stage(game, "hall")
        private = _make_home_stage(game, "private")
        private.add(PlayerOnlyStageComponent, "private")
        npc = _make_actor(game, "npc", "hall")
        result = system._get_available_home_stages(npc, current)
        assert private not in result

    def test_player_can_go_to_player_only_stage(self) -> None:
        game = _make_game()
        system = _make_system(game)
        current = _make_home_stage(game, "hall")
        private = _make_home_stage(game, "private")
        private.add(PlayerOnlyStageComponent, "private")
        player = _make_player_actor(game, "hero", "hall")
        result = system._get_available_home_stages(player, current)
        assert private in result

    def test_current_stage_always_excluded(self) -> None:
        game = _make_game()
        system = _make_system(game)
        stage = _make_home_stage(game, "home")
        _make_home_stage(game, "library")
        actor = _make_actor(game, "hero", "home")
        result = system._get_available_home_stages(actor, stage)
        assert stage not in result


# ---------------------------------------------------------------------------
# TestInjectPlayerSceneContext
# ---------------------------------------------------------------------------


class TestInjectPlayerSceneContext:
    def test_passive_player_adds_three_context_entries(self) -> None:
        # passive → mind set → notify_entities called → 3 entries (human + AI + mind)
        game = _make_game()
        system = _make_player_system(game)
        _make_home_stage(game, "home", narrative="peaceful hall")
        player = _make_player_actor(game, "hero", "home")
        before = len(game.get_agent_context(player).context)
        system._inject_player_scene_context(player, 1)
        after = len(game.get_agent_context(player).context)
        assert after == before + 3

    def test_active_player_adds_two_context_entries(self) -> None:
        # active (SpeakAction) → passive_mind="" → mind="" → no notify_entities → 2 entries
        game = _make_game()
        system = _make_player_system(game)
        _make_home_stage(game, "home", narrative="peaceful hall")
        player = _make_player_actor(game, "hero", "home")
        player.add(SpeakAction, "hero", {"npc": "hello"})
        before = len(game.get_agent_context(player).context)
        system._inject_player_scene_context(player, 1)
        after = len(game.get_agent_context(player).context)
        assert after == before + 2

    def test_uncompressed_mode_passive_player_adds_three_entries(self) -> None:
        game = _make_game()
        system = _make_player_system(game, use_compressed_prompt=False)
        _make_home_stage(game, "home", narrative="peaceful hall")
        player = _make_player_actor(game, "hero", "home")
        before = len(game.get_agent_context(player).context)
        system._inject_player_scene_context(player, 1)
        after = len(game.get_agent_context(player).context)
        assert after == before + 3


# ---------------------------------------------------------------------------
# TestInjectNpcStandbyContext
# ---------------------------------------------------------------------------


class TestInjectNpcStandbyContext:
    def test_adds_three_context_entries(self) -> None:
        # human (planning) + AI (standby) + mind notification = 3
        game = _make_game()
        system = _make_system(game)
        _make_home_stage(game, "home", narrative="quiet hall")
        npc = _make_actor(game, "npc", "home")
        before = len(game.get_agent_context(npc).context)
        system._inject_npc_standby_context(npc, 1)
        after = len(game.get_agent_context(npc).context)
        assert after == before + 3

    def test_context_contains_stage_name(self) -> None:
        game = _make_game()
        system = _make_system(game)
        _make_home_stage(game, "great_hall", narrative="echoing hall")
        npc = _make_actor(game, "npc", "great_hall")
        system._inject_npc_standby_context(npc, 1)
        ctx = game.get_agent_context(npc).context
        assert any("great_hall" in msg.content for msg in ctx)


# ---------------------------------------------------------------------------
# TestExecuteActorActions
# ---------------------------------------------------------------------------


class TestExecuteActorActions:
    def _run(
        self,
        game: TCGGame,
        system: HomeNpcPlanSystem,
        actor: Entity,
        response: dict[str, Any],
    ) -> None:
        fake = _FakeClient(actor.name, response)
        system._execute_actor_actions(actor, cast(DeepSeekClient, fake))

    def test_speak_action_added(self) -> None:
        game = _make_game()
        system = _make_system(game)
        _make_home_stage(game, "home")
        actor = _make_actor(game, "knight", "home")
        self._run(game, system, actor, _action_plan_json(speak={"npc": "hello"}))
        assert actor.has(SpeakAction)
        assert actor.get(SpeakAction).target_messages == {"npc": "hello"}

    def test_trans_stage_action_added(self) -> None:
        game = _make_game()
        system = _make_system(game)
        _make_home_stage(game, "home")
        actor = _make_actor(game, "knight", "home")
        self._run(game, system, actor, _action_plan_json(trans_stage="library"))
        assert actor.has(TransStageAction)
        assert actor.get(TransStageAction).target_stage_name == "library"

    def test_equip_weapon_action_added(self) -> None:
        game = _make_game()
        system = _make_system(game)
        _make_home_stage(game, "home")
        actor = _make_actor(game, "knight", "home")
        self._run(game, system, actor, _action_plan_json(equip_weapon="iron sword"))
        assert actor.has(EquipItemAction)
        assert actor.get(EquipItemAction).weapon == "iron sword"

    def test_query_action_added(self) -> None:
        game = _make_game()
        system = _make_system(game)
        _make_home_stage(game, "home")
        actor = _make_actor(game, "knight", "home")
        self._run(game, system, actor, _action_plan_json(query="dragon lore"))
        assert actor.has(QueryAction)
        assert actor.get(QueryAction).question == "dragon lore"

    def test_invalid_json_does_not_crash(self) -> None:
        game = _make_game()
        system = _make_system(game)
        _make_home_stage(game, "home")
        actor = _make_actor(game, "knight", "home")

        class _BadClient:
            name = "knight"
            response_content = "NOT VALID JSON !!!"
            compressed_prompt = "compressed"
            prompt = "full"
            response_ai_message: Optional[AIMessage] = AIMessage(content="bad")

        # Exception is caught inside the method; should not propagate
        system._execute_actor_actions(actor, cast(DeepSeekClient, _BadClient()))


# ---------------------------------------------------------------------------
# TestReact (integration)
# ---------------------------------------------------------------------------

_PATCH_PATH = "src.ai_rpg.systems.home_npc_plan_system.DeepSeekClient.batch_chat"


class TestReact:
    async def test_no_npc_entities_batch_chat_called_with_empty_clients(self) -> None:
        # Player filtered out before react(); with no NPC entities, batch_chat called with []
        game = _make_game()
        system = _make_system(game)
        _make_home_stage(game, "home")
        _make_player_actor(
            game, "hero", "home"
        )  # exists in game but not passed to react
        with patch(_PATCH_PATH, new_callable=AsyncMock) as mock_batch:
            await system.react([])
            mock_batch.assert_called_once_with(clients=[])

    async def test_player_active_action_puts_npc_in_standby_no_batch_chat(
        self,
    ) -> None:
        # Player entity not in entities list; _is_player_active() queries game state
        game = _make_game()
        system = _make_system(game)
        _make_home_stage(game, "home")
        player = _make_player_actor(game, "hero", "home")
        npc = _make_actor(game, "npc", "home")
        player.add(SpeakAction, "hero", {"npc": "hello"})
        with patch(_PATCH_PATH, new_callable=AsyncMock) as mock_batch:
            await system.react([npc])  # player filtered out; only NPC passed
            mock_batch.assert_not_called()
        # NPC received standby context (3 entries: human + AI + mind notify)
        npc_ctx = game.get_agent_context(npc).context
        assert len(npc_ctx) == 3

    async def test_passive_player_with_npc_calls_batch_chat(self) -> None:
        game = _make_game()
        system = _make_system(game)
        _make_home_stage(game, "home")
        _make_player_actor(game, "hero", "home")  # in game but filtered from react()
        npc = _make_actor(game, "npc", "home")
        with patch(_PATCH_PATH, new_callable=AsyncMock) as mock_batch:
            await system.react([npc])  # only NPC passed
            mock_batch.assert_called_once()
