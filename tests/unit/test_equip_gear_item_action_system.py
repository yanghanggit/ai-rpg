"""EquipGearItemActionSystem 单元测试：验证 GearItem 转化为手牌的流程。"""

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    AgentEvent,
    Card,
    EquipGearItemAction,
    HandComponent,
    InventoryComponent,
    PartyMemberComponent,
)
from src.ai_rpg.models.items import GearItem
from src.ai_rpg.systems.equip_gear_item_action_system import EquipGearItemActionSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gear(name: str) -> GearItem:
    return GearItem(name=name, description="测试装备")


def _make_actor_entity(
    context: Context,
    name: str,
    action_item: GearItem,
) -> Entity:
    """创建携带 HandComponent + PartyMemberComponent + EquipGearItemAction 的当前行动者。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(HandComponent, name, [])
    entity.add(PartyMemberComponent, name)
    entity.add(EquipGearItemAction, name, action_item)
    return entity


def _make_player_entity(context: Context, name: str, items: List[GearItem]) -> Entity:
    """创建持有团队背包（InventoryComponent）的 player 实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(InventoryComponent, name, list(items))
    return entity


def _setup_mock_game(mock_game: MagicMock, player: Entity) -> MagicMock:
    mock_game.current_dungeon_combat_room.combat.is_ongoing = True
    mock_game.current_dungeon_combat_room.combat.rounds = [MagicMock()]
    latest_round = MagicMock()
    latest_round.gear_combat_log = []
    latest_round.gear_narrative = []
    latest_round.gear_equip_count = 0
    mock_game.current_dungeon_combat_room.combat.latest_round = latest_round
    mock_game.get_player_entity.return_value = player
    return latest_round


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    return MagicMock(spec=DBGGame)


@pytest.fixture()
def system(mock_game: MagicMock) -> EquipGearItemActionSystem:
    return EquipGearItemActionSystem(mock_game)


# ---------------------------------------------------------------------------
# react()
# ---------------------------------------------------------------------------


class TestReact:
    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: Context,
        mock_game: MagicMock,
        system: EquipGearItemActionSystem,
    ) -> None:
        mock_game.current_dungeon_combat_room.combat.is_ongoing = False
        gear = _make_gear("装备.测试")
        actor = _make_actor_entity(context, "角色.测试", gear)

        await system.react([actor])

        mock_game.get_player_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_converts_gear_to_hand_card(
        self,
        context: Context,
        mock_game: MagicMock,
        system: EquipGearItemActionSystem,
    ) -> None:
        gear = _make_gear("装备.测试")
        actor = _make_actor_entity(context, "角色.测试", gear)
        player = _make_player_entity(context, "player", [gear])
        latest_round = _setup_mock_game(mock_game, player)
        stage = context.create_entity()
        stage._name = "测试场景"
        mock_game.resolve_stage_entity.return_value = stage

        generated = Card(name="斩击", description="x")
        with patch.object(
            system, "_generate_card", new=AsyncMock(return_value=generated)
        ):
            await system.react([actor])

        # 移动语义：gear 从团队背包移除
        assert gear not in player.get(InventoryComponent).items
        # 生成的卡牌进入当前行动者手牌
        assert generated in actor.get(HandComponent).cards
        # 本回合装备使用结果被记录
        assert latest_round.gear_equip_count == 1
        assert latest_round.gear_combat_log
        assert latest_round.gear_narrative
        # 广播装备转化通知
        mock_game.broadcast_to_stage.assert_called_once()
        _, kwargs = mock_game.broadcast_to_stage.call_args
        assert kwargs["entity"] is actor
        assert kwargs["exclude_entities"] == {stage}
        assert isinstance(kwargs["agent_event"], AgentEvent)
