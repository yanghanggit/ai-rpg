"""CombatRoundCleanupSystem 单元测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from typing import List

from src.ai_rpg.deepseek import AIMessage, DeepSeekClient
from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.tcg_game import TCGGame
from src.ai_rpg.models import (
    ActorComponent,
    CharacterStatsComponent,
    StatusEffectsComponent,
)
from src.ai_rpg.models import CharacterStats
from src.ai_rpg.models import CombatPhase, StatusEffect
from src.ai_rpg.systems.combat_round_cleanup_system import (
    CombatRoundCleanupSystem,
    _make_status_effects_tick_message,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_effect(name: str, duration: int) -> StatusEffect:
    """创建测试用 ARBITRATION 阶段状态效果。"""
    return StatusEffect(
        name=name,
        description="test",
        phase=CombatPhase.ARBITRATION,
        duration=duration,
    )


def _make_round_end_effect(name: str, duration: int) -> StatusEffect:
    """创建测试用 ROUND_END 阶段状态效果（DOT/HOT）。"""
    return StatusEffect(
        name=name,
        description=f"{name}发作，持续伤害",
        phase=CombatPhase.ROUND_END,
        duration=duration,
    )


def _make_actor_with_effects(
    context: Context, name: str, effects: List[StatusEffect]
) -> Entity:
    """创建挂载 ActorComponent + StatusEffectsComponent 的角色实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "sheet", "stage")
    entity.add(StatusEffectsComponent, name, effects)
    return entity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    """提供真实 ECS Context，使 Group 自动更新行为正确生效。"""
    return Context()


@pytest.fixture()
def mock_game(context: Context) -> MagicMock:
    """MagicMock TCGGame，将 get_group() 代理到真实 Context。"""
    game = MagicMock(spec=TCGGame)
    game.get_group.side_effect = context.get_group
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> CombatRoundCleanupSystem:
    return CombatRoundCleanupSystem(mock_game)


# ---------------------------------------------------------------------------
# Phase 1 — 纯函数测试
# ---------------------------------------------------------------------------


class TestMakeStatusEffectsTickMessage:
    """_make_status_effects_tick_message 的单元测试。"""

    def test_ticked_effect_shows_remaining_duration(self) -> None:
        """递减后仍存活的效果应显示剩余回合数。"""
        effect = _make_effect("中毒", 2)
        result = _make_status_effects_tick_message([effect], [])
        assert "中毒" in result
        assert "2" in result

    def test_expired_effect_shows_expired_text(self) -> None:
        """已过期的效果应包含"已过期"字样。"""
        effect = _make_effect("燃烧", 0)
        result = _make_status_effects_tick_message([], [effect])
        assert "燃烧" in result
        assert "已过期" in result

    def test_mixed_shows_both(self) -> None:
        """ticked 与 expired 混合时，两者信息均应出现。"""
        ticked = _make_effect("中毒", 1)
        expired = _make_effect("燃烧", 0)
        result = _make_status_effects_tick_message([ticked], [expired])
        assert "中毒" in result
        assert "燃烧" in result
        assert "已过期" in result

    def test_empty_lists_returns_header_only(self) -> None:
        """ticked 与 expired 均为空时，仍返回非空标题行。"""
        result = _make_status_effects_tick_message([], [])
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Phase 2 — tick_status_effects_duration 测试
# ---------------------------------------------------------------------------


class TestTickStatusEffectsDuration:
    """tick_status_effects_duration 的单元测试。"""

    def test_permanent_effect_not_decremented(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatRoundCleanupSystem,
    ) -> None:
        """duration == -1 的永久效果不应被递减，也不应触发 add_human_message。"""
        effect = _make_effect("永久祝福", -1)
        _make_actor_with_effects(context, "英雄", [effect])

        system.tick_status_effects_duration()

        mock_game.add_human_message.assert_not_called()
        # 效果仍在，duration 不变
        assert effect.duration == -1

    def test_effect_with_duration_one_expires(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatRoundCleanupSystem,
    ) -> None:
        """duration == 1 的效果递减后应从列表中移除，并调用 add_human_message。"""
        effect = _make_effect("中毒", 1)
        actor = _make_actor_with_effects(context, "英雄", [effect])

        system.tick_status_effects_duration()

        comp = actor.get(StatusEffectsComponent)
        assert len(comp.status_effects) == 0
        mock_game.add_human_message.assert_called_once()

    def test_effect_with_duration_two_decrements(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatRoundCleanupSystem,
    ) -> None:
        """duration == 2 的效果递减后应保留（duration 变为 1），并调用 add_human_message。"""
        effect = _make_effect("减速", 2)
        actor = _make_actor_with_effects(context, "英雄", [effect])

        system.tick_status_effects_duration()

        comp = actor.get(StatusEffectsComponent)
        assert len(comp.status_effects) == 1
        assert comp.status_effects[0].duration == 1
        mock_game.add_human_message.assert_called_once()

    def test_mixed_effects_handled_correctly(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatRoundCleanupSystem,
    ) -> None:
        """永久、将过期、继续存活的效果混合时应各自正确处理。"""
        permanent = _make_effect("祝福", -1)
        expiring = _make_effect("燃烧", 1)
        continuing = _make_effect("中毒", 3)
        actor = _make_actor_with_effects(
            context, "英雄", [permanent, expiring, continuing]
        )

        system.tick_status_effects_duration()

        comp = actor.get(StatusEffectsComponent)
        remaining_names = {e.name for e in comp.status_effects}
        assert "祝福" in remaining_names
        assert "中毒" in remaining_names
        assert "燃烧" not in remaining_names

    def test_no_change_skips_add_human_message(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatRoundCleanupSystem,
    ) -> None:
        """所有效果均为永久时，add_human_message 不应被调用。"""
        p1 = _make_effect("祝福", -1)
        p2 = _make_effect("庇护", -1)
        _make_actor_with_effects(context, "英雄", [p1, p2])

        system.tick_status_effects_duration()

        mock_game.add_human_message.assert_not_called()

    def test_multiple_actors_each_processed(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatRoundCleanupSystem,
    ) -> None:
        """多角色时，每个有变化的角色均应调用一次 add_human_message。"""
        _make_actor_with_effects(context, "英雄", [_make_effect("中毒", 1)])
        _make_actor_with_effects(context, "同伴", [_make_effect("燃烧", 1)])

        system.tick_status_effects_duration()

        assert mock_game.add_human_message.call_count == 2


# ---------------------------------------------------------------------------
# Phase 3 — execute() 编排逻辑测试
# ---------------------------------------------------------------------------


class TestExecute:
    """CombatRoundCleanupSystem.execute() 的单元测试。"""

    @pytest.mark.asyncio
    async def test_skip_when_not_ongoing(
        self, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        """战斗非 ONGOING 时，clear_round_state 不应被调用。"""
        mock_game.current_dungeon.is_ongoing = False
        await system.execute()
        mock_game.clear_round_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_no_rounds(
        self, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        """无任何回合记录时，clear_round_state 不应被调用。"""
        mock_game.current_dungeon.is_ongoing = True
        mock_game.current_dungeon.current_rounds = []
        await system.execute()
        mock_game.clear_round_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_round_not_completed(
        self, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        """最新回合未完成时，clear_round_state 不应被调用。"""
        mock_game.current_dungeon.is_ongoing = True
        mock_game.current_dungeon.current_rounds = [MagicMock()]
        mock_game.current_dungeon.latest_round.is_completed = False
        await system.execute()
        mock_game.clear_round_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_clears_state_when_round_completed(
        self, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        """最新回合已完成时，clear_round_state 应被调用一次。"""
        mock_game.current_dungeon.is_ongoing = True
        mock_game.current_dungeon.current_rounds = [MagicMock()]
        mock_game.current_dungeon.latest_round.is_completed = True
        await system.execute()
        mock_game.clear_round_state.assert_called_once()


# ---------------------------------------------------------------------------
# Phase 4 — process_round_end_effects() 测试
# ---------------------------------------------------------------------------


def _make_actor_with_stats_and_effects(
    context: Context,
    name: str,
    effects: List[StatusEffect],
) -> Entity:
    """创建挂载 ActorComponent + CharacterStatsComponent + StatusEffectsComponent 的实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "sheet", "stage")
    entity.add(CharacterStatsComponent, name, CharacterStats(hp=20, max_hp=30))
    entity.add(StatusEffectsComponent, name, effects)
    return entity


def _make_mock_game_with_stats(context: Context) -> MagicMock:
    """构造带有统计信息 mock 的 TCGGame，compute_character_stats 返回 hp=20, max_hp=30。"""
    game = MagicMock(spec=TCGGame)
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

    game.process_zero_health_entities = MagicMock()

    return game


class TestProcessRoundEndEffects:
    """process_round_end_effects() 的单元测试。"""

    @pytest.mark.asyncio
    async def test_no_round_end_effects_skips_llm(
        self,
        context: Context,
    ) -> None:
        """实体只有 ARBITRATION 效果时，不应创建 chat client（batch_chat 不被调用）。"""
        game = _make_mock_game_with_stats(context)
        system = CombatRoundCleanupSystem(game)
        _make_actor_with_stats_and_effects(context, "英雄", [_make_effect("虚弱", 2)])

        with patch(
            "src.ai_rpg.systems.combat_round_cleanup_system.DeepSeekClient.batch_chat",
            new_callable=AsyncMock,
        ) as mock_batch_chat:
            await system.process_round_end_effects()
            mock_batch_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_round_end_effects_calls_batch_chat(
        self,
        context: Context,
    ) -> None:
        """实体有 ROUND_END 效果时，batch_chat 应被调用一次。"""
        game = _make_mock_game_with_stats(context)
        game.get_entity_by_name.return_value = (
            None  # 防止 assert 失败；响应处理会 logger.error
        )

        entity = _make_actor_with_stats_and_effects(
            context, "英雄", [_make_round_end_effect("中毒", 3)]
        )
        game.get_entity_by_name.return_value = entity

        with patch(
            "src.ai_rpg.systems.combat_round_cleanup_system.DeepSeekClient.batch_chat",
            new_callable=AsyncMock,
        ) as mock_batch_chat:
            await CombatRoundCleanupSystem(game).process_round_end_effects()
            mock_batch_chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_only_round_end_effects_included(
        self,
        context: Context,
    ) -> None:
        """ARBITRATION 效果不应出现在发送给 LLM 的 prompt 中。"""
        game = _make_mock_game_with_stats(context)

        entity = _make_actor_with_stats_and_effects(
            context,
            "英雄",
            [_make_round_end_effect("中毒", 3), _make_effect("虚弱", 2)],
        )
        game.get_entity_by_name.return_value = entity

        captured_clients: List[DeepSeekClient] = []

        async def capture_clients(clients: List[DeepSeekClient]) -> None:
            captured_clients.extend(clients)

        with patch(
            "src.ai_rpg.systems.combat_round_cleanup_system.DeepSeekClient.batch_chat",
            side_effect=capture_clients,
        ):
            await CombatRoundCleanupSystem(game).process_round_end_effects()

        assert len(captured_clients) == 1
        assert "中毒" in captured_clients[0]._prompt
        assert "虚弱" not in captured_clients[0]._prompt

    @pytest.mark.asyncio
    async def test_hp_updated_after_llm_response(
        self,
        context: Context,
    ) -> None:
        """LLM 返回合法 JSON 后，set_character_hp 应被调用。"""
        game = _make_mock_game_with_stats(context)
        entity = _make_actor_with_stats_and_effects(
            context, "英雄", [_make_round_end_effect("中毒", 3)]
        )
        game.get_entity_by_name.return_value = entity

        async def fake_batch_chat(clients: List[DeepSeekClient]) -> None:
            for client in clients:
                client._response_ai_message = AIMessage(
                    content='{"hp": 17, "combat_log": "中毒发作，扣除3HP"}'
                )

        with patch(
            "src.ai_rpg.systems.combat_round_cleanup_system.DeepSeekClient.batch_chat",
            side_effect=fake_batch_chat,
        ):
            await CombatRoundCleanupSystem(game).process_round_end_effects()

        game.set_character_hp.assert_called_once_with(entity, 17)

    @pytest.mark.asyncio
    async def test_concurrent_clients_per_entity(
        self,
        context: Context,
    ) -> None:
        """多实体各有 ROUND_END 效果时，batch_chat 应收到对应数量的 client。"""
        game = _make_mock_game_with_stats(context)

        e1 = _make_actor_with_stats_and_effects(
            context, "英雄", [_make_round_end_effect("中毒", 3)]
        )
        e2 = _make_actor_with_stats_and_effects(
            context, "同伴", [_make_round_end_effect("燃烧", 2)]
        )
        game.get_entity_by_name.side_effect = lambda name: (
            e1 if name == "英雄" else e2
        )

        captured_clients: List[DeepSeekClient] = []

        async def capture_clients(clients: List[DeepSeekClient]) -> None:
            captured_clients.extend(clients)

        with patch(
            "src.ai_rpg.systems.combat_round_cleanup_system.DeepSeekClient.batch_chat",
            side_effect=capture_clients,
        ):
            await CombatRoundCleanupSystem(game).process_round_end_effects()

        assert len(captured_clients) == 2
        names = {c.name for c in captured_clients}
        assert names == {"英雄", "同伴"}

    @pytest.mark.asyncio
    async def test_zero_health_entities_called_after_hp_update(
        self,
        context: Context,
    ) -> None:
        """HP 更新后应调用 process_zero_health_entities。"""
        game = _make_mock_game_with_stats(context)
        entity = _make_actor_with_stats_and_effects(
            context, "英雄", [_make_round_end_effect("中毒", 3)]
        )
        game.get_entity_by_name.return_value = entity

        async def fake_batch_chat(clients: List[DeepSeekClient]) -> None:
            for client in clients:
                client._response_ai_message = AIMessage(
                    content='{"hp": 0, "combat_log": "中毒致死"}'
                )

        with patch(
            "src.ai_rpg.systems.combat_round_cleanup_system.DeepSeekClient.batch_chat",
            side_effect=fake_batch_chat,
        ):
            await CombatRoundCleanupSystem(game).process_round_end_effects()

        game.process_zero_health_entities.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_parse_error_does_not_raise(
        self,
        context: Context,
    ) -> None:
        """LLM 返回无法解析的内容时，不应抛出异常（仅 logger.error）。"""
        game = _make_mock_game_with_stats(context)
        entity = _make_actor_with_stats_and_effects(
            context, "英雄", [_make_round_end_effect("中毒", 3)]
        )
        game.get_entity_by_name.return_value = entity

        async def fake_batch_chat_bad(clients: List[DeepSeekClient]) -> None:
            for client in clients:
                client._response_ai_message = AIMessage(content="这不是有效的JSON")

        with patch(
            "src.ai_rpg.systems.combat_round_cleanup_system.DeepSeekClient.batch_chat",
            side_effect=fake_batch_chat_bad,
        ):
            # 不应抛出异常
            await CombatRoundCleanupSystem(game).process_round_end_effects()

        game.set_character_hp.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_calls_round_end_before_tick(
        self,
        context: Context,
    ) -> None:
        """execute() 中 process_round_end_effects 应在 tick_status_effects_duration 之前调用。"""
        game = _make_mock_game_with_stats(context)
        game.current_dungeon.is_ongoing = True
        game.current_dungeon.current_rounds = [MagicMock()]
        game.current_dungeon.latest_round.is_completed = True

        system = CombatRoundCleanupSystem(game)
        call_order: List[str] = []

        original_round_end = system.process_round_end_effects
        original_tick = system.tick_status_effects_duration

        async def track_round_end() -> None:
            call_order.append("round_end")
            await original_round_end()

        def track_tick() -> None:
            call_order.append("tick")
            original_tick()

        setattr(system, "process_round_end_effects", track_round_end)
        setattr(system, "tick_status_effects_duration", track_tick)

        await system.execute()

        assert call_order == ["round_end", "tick"]
