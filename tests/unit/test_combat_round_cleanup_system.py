"""CombatRoundCleanupSystem 单元测试。"""

import pytest
from unittest.mock import MagicMock
from typing import List

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.entitas import Matcher
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    CharacterStatsComponent,
    StatusEffectsComponent,
)
from src.ai_rpg.models import CharacterStats
from src.ai_rpg.models import PhaseType, StatusEffect
from src.ai_rpg.models.messages import AIMessage
from src.ai_rpg.deepseek import DeepSeekClient
from src.ai_rpg.systems.combat_round_cleanup_system import (
    CombatRoundCleanupSystem,
    _make_status_effects_tick_message,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_effect(name: str, duration: int) -> StatusEffect:
    return StatusEffect(
        name=name, description="test", phase=PhaseType.ARBITRATION, duration=duration
    )


def _make_round_end_effect(name: str, duration: int) -> StatusEffect:
    return StatusEffect(
        name=name,
        description=f"{name}发作",
        phase=PhaseType.ROUND_END,
        duration=duration,
    )


def _make_actor(context: Context, name: str, effects: List[StatusEffect]) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "sheet", "stage")
    entity.add(StatusEffectsComponent, name, effects)
    return entity


def _make_actor_with_stats(
    context: Context, name: str, effects: List[StatusEffect]
) -> Entity:
    entity = _make_actor(context, name, effects)
    entity.add(CharacterStatsComponent, name, CharacterStats(hp=20, max_hp=30))
    return entity


def _make_mock_game(context: Context) -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.get_group.side_effect = context.get_group

    stats = MagicMock()
    stats.hp = 20
    stats.max_hp = 30
    game.compute_character_stats.return_value = stats

    after_stats = MagicMock()
    after_stats.hp = 17
    after_stats.max_hp = 30
    game.set_character_hp.return_value = after_stats

    agent_ctx = MagicMock()
    agent_ctx.context = []
    game.get_agent_context.return_value = agent_ctx

    return game


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game(context: Context) -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.get_group.side_effect = context.get_group
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> CombatRoundCleanupSystem:
    return CombatRoundCleanupSystem(mock_game)


# ---------------------------------------------------------------------------
# _make_status_effects_tick_message
# ---------------------------------------------------------------------------


class TestMakeStatusEffectsTickMessage:

    def test_ticked_shows_remaining_duration(self) -> None:
        result = _make_status_effects_tick_message([_make_effect("中毒", 2)], [])
        assert "中毒" in result and "2" in result

    def test_expired_shows_expired_text(self) -> None:
        result = _make_status_effects_tick_message([], [_make_effect("燃烧", 0)])
        assert "燃烧" in result and "已过期" in result

    def test_mixed_shows_both(self) -> None:
        result = _make_status_effects_tick_message(
            [_make_effect("中毒", 1)], [_make_effect("燃烧", 0)]
        )
        assert "中毒" in result and "燃烧" in result and "已过期" in result

    def test_empty_returns_nonempty_header(self) -> None:
        assert len(_make_status_effects_tick_message([], [])) > 0


# ---------------------------------------------------------------------------
# tick_status_effects_duration
# ---------------------------------------------------------------------------


class TestTickStatusEffectsDuration:

    def test_permanent_not_decremented_no_message(
        self, context: Context, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        """duration == -1 永久效果不递减，也不写上下文。"""
        effect = _make_effect("永久祝福", -1)
        _make_actor(context, "英雄", [effect])

        system.tick_status_effects_duration()

        assert effect.duration == -1
        mock_game.add_human_message.assert_not_called()

    def test_duration_one_expires_and_writes_message(
        self, context: Context, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        """duration == 1 效果到期后从列表移除，调用一次 add_human_message。"""
        actor = _make_actor(context, "英雄", [_make_effect("中毒", 1)])

        system.tick_status_effects_duration()

        assert len(actor.get(StatusEffectsComponent).status_effects) == 0
        mock_game.add_human_message.assert_called_once()

    def test_duration_two_decrements_to_one(
        self, context: Context, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        """duration == 2 效果递减为 1 后保留，调用一次 add_human_message。"""
        actor = _make_actor(context, "英雄", [_make_effect("减速", 2)])

        system.tick_status_effects_duration()

        remaining = actor.get(StatusEffectsComponent).status_effects
        assert len(remaining) == 1 and remaining[0].duration == 1
        mock_game.add_human_message.assert_called_once()

    def test_mixed_effects_handled_independently(
        self, context: Context, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        """永久/到期/存活效果混合时各自正确处理。"""
        actor = _make_actor(
            context,
            "英雄",
            [
                _make_effect("祝福", -1),
                _make_effect("燃烧", 1),
                _make_effect("中毒", 3),
            ],
        )

        system.tick_status_effects_duration()

        names = {e.name for e in actor.get(StatusEffectsComponent).status_effects}
        assert names == {"祝福", "中毒"}

    def test_multiple_actors_each_get_message(
        self, context: Context, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        """多角色各有到期效果时，每个角色调用一次 add_human_message。"""
        _make_actor(context, "英雄", [_make_effect("中毒", 1)])
        _make_actor(context, "同伴", [_make_effect("燃烧", 1)])

        system.tick_status_effects_duration()

        assert mock_game.add_human_message.call_count == 2


# ---------------------------------------------------------------------------
# execute() 编排逻辑
# ---------------------------------------------------------------------------


class TestExecute:

    @pytest.mark.asyncio
    async def test_skip_when_not_ongoing(
        self, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        mock_game.current_dungeon.is_ongoing = False
        await system.execute()
        mock_game.clear_round_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_no_rounds(
        self, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        mock_game.current_dungeon.is_ongoing = True
        mock_game.current_dungeon.current_rounds = []
        await system.execute()
        mock_game.clear_round_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_round_not_completed(
        self, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        mock_game.current_dungeon.is_ongoing = True
        mock_game.current_dungeon.current_rounds = [MagicMock()]
        mock_game.current_dungeon.latest_round.is_completed = False
        await system.execute()
        mock_game.clear_round_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_clears_state_when_round_completed(
        self, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        mock_game.current_dungeon.is_ongoing = True
        mock_game.current_dungeon.current_rounds = [MagicMock()]
        mock_game.current_dungeon.latest_round.is_completed = True
        await system.execute()
        mock_game.clear_round_state.assert_called_once()


# ---------------------------------------------------------------------------
# _create_round_end_effect_client
# ---------------------------------------------------------------------------


class TestCreateRoundEndEffectClient:

    def test_returns_none_when_no_round_end_effects(self, context: Context) -> None:
        """只有 ARBITRATION 效果时返回 None，不创建 client。"""
        game = _make_mock_game(context)
        system = CombatRoundCleanupSystem(game)
        _make_actor_with_stats(context, "英雄", [_make_effect("虚弱", 2)])
        entity = next(iter(context.get_group(Matcher(StatusEffectsComponent)).entities))

        assert system._create_round_end_effect_client(entity) is None

    def test_returns_configured_client_for_round_end_effects(
        self, context: Context
    ) -> None:
        """有 ROUND_END 效果时返回 DeepSeekClient，name 匹配且 prompt 包含效果名。"""
        game = _make_mock_game(context)
        system = CombatRoundCleanupSystem(game)
        _make_actor_with_stats(context, "英雄", [_make_round_end_effect("中毒", 3)])
        entity = next(iter(context.get_group(Matcher(StatusEffectsComponent)).entities))

        client = system._create_round_end_effect_client(entity)

        assert client is not None
        assert client.name == "英雄"
        assert "中毒" in client.prompt


# ---------------------------------------------------------------------------
# _apply_round_end_effect_response
# ---------------------------------------------------------------------------


class TestApplyRoundEndEffectResponse:

    def test_valid_response_updates_hp(self, context: Context) -> None:
        """LLM 返回合法 JSON 时 set_character_hp 应被调用。"""
        game = _make_mock_game(context)
        entity = _make_actor_with_stats(context, "英雄", [])
        game.get_entity_by_name.return_value = entity
        system = CombatRoundCleanupSystem(game)

        client = MagicMock(spec=DeepSeekClient)
        client.name = "英雄"
        client.prompt = "test prompt"
        client.response_content = '{"hp": 17, "combat_log": "中毒发作，扣除3HP"}'
        client.response_ai_message = AIMessage(content=client.response_content)

        system._apply_round_end_effect_response(client)

        game.set_character_hp.assert_called_once_with(entity, 17)

    def test_invalid_response_does_not_raise(self, context: Context) -> None:
        """LLM 返回无法解析的内容时不抛出异常，set_character_hp 不被调用。"""
        game = _make_mock_game(context)
        entity = _make_actor_with_stats(context, "英雄", [])
        game.get_entity_by_name.return_value = entity
        system = CombatRoundCleanupSystem(game)

        client = MagicMock(spec=DeepSeekClient)
        client.name = "英雄"
        client.prompt = "test prompt"
        client.response_content = "这不是有效的JSON"

        system._apply_round_end_effect_response(client)  # 不应抛出

        game.set_character_hp.assert_not_called()
