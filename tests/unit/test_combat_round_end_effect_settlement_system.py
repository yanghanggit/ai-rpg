"""CombatRoundEndEffectSettlementSystem 单元测试。"""

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai_rpg.deepseek import DeepSeekClient
from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    CharacterStatsComponent,
    PhaseType,
    StatusEffect,
    StatusEffectsComponent,
)
from src.ai_rpg.models.messages import AIMessage
from src.ai_rpg.models.stats import CharacterStats
from src.ai_rpg.systems.combat_round_end_effect_settlement_system import (
    CombatRoundEndEffectSettlementSystem,
    _make_round_end_hp_update_message,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _effect(name: str, duration: int) -> StatusEffect:
    return StatusEffect(
        name=name, description="test", phase=PhaseType.ARBITRATION, duration=duration
    )


def _make_actor(ctx: Context, name: str, effects: List[StatusEffect]) -> Entity:
    entity = ctx.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "sheet", "stage")
    entity.add(StatusEffectsComponent, name, effects)
    return entity


def _make_game(ctx: Context) -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.get_group.side_effect = ctx.get_group
    return game


def _make_client(name: str, json_str: str) -> MagicMock:
    client = MagicMock(spec=DeepSeekClient)
    client.name = name
    client.prompt = "prompt"
    client.response_content = json_str
    client.response_ai_message = AIMessage(content=json_str)
    return client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ctx() -> Context:
    return Context()


@pytest.fixture()
def game(ctx: Context) -> MagicMock:
    return _make_game(ctx)


@pytest.fixture()
def system(game: MagicMock) -> CombatRoundEndEffectSettlementSystem:
    return CombatRoundEndEffectSettlementSystem(game)


# ---------------------------------------------------------------------------
# _make_round_end_hp_update_message
# ---------------------------------------------------------------------------


def test_round_end_hp_message_contains_values() -> None:
    result = _make_round_end_hp_update_message(17, 30)
    assert "17" in result and "30" in result


# ---------------------------------------------------------------------------
# _apply_round_end_effect_response
# ---------------------------------------------------------------------------


@patch("src.ai_rpg.systems.combat_round_end_effect_settlement_system.set_character_hp")
def test_apply_valid_response_updates_hp(mock_set_hp: MagicMock, ctx: Context) -> None:
    """LLM 返回合法 JSON 时 set_character_hp 应被调用。"""
    game = _make_game(ctx)
    entity = _make_actor(ctx, "英雄", [])
    entity.add(CharacterStatsComponent, "英雄", CharacterStats(hp=20, max_hp=30))
    game.get_entity_by_name.return_value = entity
    mock_set_hp.return_value = MagicMock(hp=17, max_hp=30)
    system = CombatRoundEndEffectSettlementSystem(game)

    system._apply_round_end_effect_response(
        _make_client("英雄", '{"hp": 17, "combat_log": "中毒发作"}')
    )

    mock_set_hp.assert_called_once_with(entity, 17)


@patch("src.ai_rpg.systems.combat_round_end_effect_settlement_system.set_character_hp")
def test_apply_invalid_response_no_raise(mock_set_hp: MagicMock, ctx: Context) -> None:
    """LLM 返回无法解析的内容时不抛出，set_character_hp 不被调用。"""
    game = _make_game(ctx)
    entity = _make_actor(ctx, "英雄", [])
    entity.add(CharacterStatsComponent, "英雄", CharacterStats(hp=20, max_hp=30))
    game.get_entity_by_name.return_value = entity
    system = CombatRoundEndEffectSettlementSystem(game)

    system._apply_round_end_effect_response(_make_client("英雄", "not valid json"))

    mock_set_hp.assert_not_called()


# ---------------------------------------------------------------------------
# execute() 编排逻辑
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skips_when_not_ongoing(
    game: MagicMock, system: CombatRoundEndEffectSettlementSystem
) -> None:
    game.current_combat_room.combat.is_ongoing = False
    await system.execute()
    game.get_group.assert_not_called()


@pytest.mark.asyncio
async def test_execute_skips_when_no_rounds(
    game: MagicMock, system: CombatRoundEndEffectSettlementSystem
) -> None:
    game.current_combat_room.combat.is_ongoing = True
    game.current_combat_room.combat.rounds = []
    await system.execute()
    game.get_group.assert_not_called()


@pytest.mark.asyncio
async def test_execute_skips_when_round_not_completed(
    game: MagicMock, system: CombatRoundEndEffectSettlementSystem
) -> None:
    game.current_combat_room.combat.is_ongoing = True
    game.current_combat_room.combat.rounds = [MagicMock()]
    game.current_combat_room.combat.latest_round.is_completed = False
    await system.execute()
    game.get_group.assert_not_called()


@pytest.mark.asyncio
async def test_execute_processes_zero_health_entities_when_completed(
    ctx: Context, game: MagicMock, system: CombatRoundEndEffectSettlementSystem
) -> None:
    """回合完成时应并发结算 ROUND_END 效果，并调用死亡结算。"""
    game.current_combat_room.combat.is_ongoing = True
    game.current_combat_room.combat.rounds = [MagicMock()]
    game.current_combat_room.combat.latest_round.is_completed = True
    # 无任何持有 ROUND_END 效果的实体，chat_clients 为空列表
    with (
        patch(
            "src.ai_rpg.systems.combat_round_end_effect_settlement_system.DeepSeekClient.batch_chat",
            new_callable=AsyncMock,
        ) as mock_batch_chat,
        patch(
            "src.ai_rpg.systems.combat_round_end_effect_settlement_system.process_zero_health_entities"
        ) as mock_process_zero_health,
    ):
        await system.execute()

    mock_batch_chat.assert_awaited_once_with(clients=[])
    mock_process_zero_health.assert_called_once_with(game)
