"""UseGearItemActionSystem 单元测试：验证以 energy 消耗替代耐久约束的装备机制。"""

from typing import List
from unittest.mock import MagicMock

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    AgentEvent,
    EquippedGearComponent,
    InventoryComponent,
    PartyMemberComponent,
    RoundStatsComponent,
    UseGearItemAction,
)
from src.ai_rpg.models.items import GearItem
from src.ai_rpg.systems.use_gear_item_action_system import UseGearItemActionSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gear(name: str, cost: int = 1) -> GearItem:
    return GearItem(
        name=name,
        description="测试装备",
        cost=cost,
    )


def _make_player_entity(
    context: Context,
    name: str,
    items: List[GearItem],
    action_item: GearItem,
    targets: List[str],
) -> Entity:
    """创建持有 InventoryComponent + UseGearItemAction 的 player 实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(InventoryComponent, name, list(items))
    entity.add(UseGearItemAction, name, action_item, targets)
    return entity


def _make_party_entity(context: Context, name: str, energy: int) -> Entity:
    """创建带 RoundStatsComponent（当前回合剩余 energy）的友方角色实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(PartyMemberComponent, name)
    entity.add(RoundStatsComponent, name, energy)
    return entity


def _setup_mock_dungeon(mock_game: MagicMock, *, round_count: int = 1) -> None:
    mock_game.current_combat_room.combat.is_ongoing = True
    mock_game.current_combat_room.combat.rounds = [MagicMock()] * round_count


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
def system(mock_game: MagicMock) -> UseGearItemActionSystem:
    return UseGearItemActionSystem(mock_game)


# ---------------------------------------------------------------------------
# react()
# ---------------------------------------------------------------------------


class TestReact:
    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseGearItemActionSystem,
    ) -> None:
        mock_game.current_combat_room.combat.is_ongoing = False
        gear = _make_gear("装备.测试")
        player = _make_player_entity(context, "player", [gear], gear, ["队友A"])

        await system.react([player])

        mock_game.get_entity_by_name.assert_not_called()

    @pytest.mark.asyncio
    async def test_target_energy_deducted_by_item_cost(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseGearItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game)
        gear = _make_gear("装备.测试", cost=2)
        player = _make_player_entity(context, "player", [gear], gear, ["队友A"])
        target = _make_party_entity(context, "队友A", energy=3)
        stage = context.create_entity()
        stage._name = "测试场景"
        mock_game.get_entity_by_name.return_value = target
        mock_game.resolve_stage_entity.return_value = stage

        await system.react([player])

        assert target.get(RoundStatsComponent).energy == 1
        assert target.get(EquippedGearComponent).item.name == "装备.测试"
        assert target.get(EquippedGearComponent).item is gear
        assert gear not in player.get(InventoryComponent).items
        mock_game.broadcast_to_stage.assert_called_once()
        _, kwargs = mock_game.broadcast_to_stage.call_args
        assert kwargs["entity"] is player
        assert kwargs["exclude_entities"] == {stage}
        assert isinstance(kwargs["agent_event"], AgentEvent)
        assert kwargs["agent_event"].message == (
            "【第 1 回合 · 装备行动】\n「队友A」装备了「装备.测试」。"
        )

    @pytest.mark.asyncio
    async def test_swapping_gear_returns_previous_item_to_owner_inventory(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseGearItemActionSystem,
    ) -> None:
        """目标已装备旧装备时，再次为其装备新装备应将旧装备归还背包持有者
        （移动语义下的换装场景，对齐 WornCostumeComponent 的换装行为）。"""
        _setup_mock_dungeon(mock_game)
        new_gear = _make_gear("装备.新", cost=1)
        old_gear = _make_gear("装备.旧", cost=1)
        player = _make_player_entity(context, "player", [new_gear], new_gear, ["队友A"])
        target = _make_party_entity(context, "队友A", energy=2)
        target.add(EquippedGearComponent, target.name, old_gear)
        stage = context.create_entity()
        stage._name = "测试场景"
        mock_game.get_entity_by_name.return_value = target
        mock_game.resolve_stage_entity.return_value = stage

        await system.react([player])

        assert target.get(EquippedGearComponent).item is new_gear
        assert old_gear in player.get(InventoryComponent).items
        assert new_gear not in player.get(InventoryComponent).items

    @pytest.mark.asyncio
    async def test_does_not_affect_other_holders_equipped_gear(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseGearItemActionSystem,
    ) -> None:
        """为一个目标装备新装备，不应影响其它已装备角色的 EquippedGearComponent。"""
        _setup_mock_dungeon(mock_game)
        action_gear = _make_gear("装备.测试", cost=1)
        other_holder_gear = _make_gear("装备.测试", cost=1)
        player = _make_player_entity(
            context, "player", [action_gear], action_gear, ["队友A"]
        )
        target = _make_party_entity(context, "队友A", energy=2)
        other_holder = _make_party_entity(context, "队友B", energy=2)
        stage = context.create_entity()
        stage._name = "测试场景"
        other_holder.add(EquippedGearComponent, other_holder.name, other_holder_gear)
        mock_game.get_entity_by_name.return_value = target
        mock_game.resolve_stage_entity.return_value = stage

        await system.react([player])

        assert other_holder.has(EquippedGearComponent)
        assert other_holder.get(EquippedGearComponent).item is other_holder_gear
        assert target.get(EquippedGearComponent).item is action_gear

    @pytest.mark.asyncio
    async def test_raises_when_target_energy_less_than_item_cost(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseGearItemActionSystem,
    ) -> None:
        """系统信任调用方（activate_use_gear）已校验目标 energy>=cost；
        若目标 energy 不足仍被调用，系统层断言应失败。"""
        _setup_mock_dungeon(mock_game)
        gear = _make_gear("装备.测试", cost=2)
        player = _make_player_entity(context, "player", [gear], gear, ["队友A"])
        target = _make_party_entity(context, "队友A", energy=1)
        mock_game.get_entity_by_name.return_value = target

        with pytest.raises(AssertionError):
            await system.react([player])
