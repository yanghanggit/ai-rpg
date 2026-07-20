"""UseConsumableItemActionSystem 单元测试。"""

from typing import List
from unittest.mock import MagicMock

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    AgentEvent,
    InventoryComponent,
    UseConsumableItemAction,
)
from src.ai_rpg.models.items import ConsumableItem
from src.ai_rpg.models.target_type import TargetType
from src.ai_rpg.systems.use_consumable_item_action_system import (
    UseConsumableItemActionSystem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_consumable(
    name: str,
    *,
    count: int = 1,
    target_type: TargetType = TargetType.SELF_ONLY,
) -> ConsumableItem:
    return ConsumableItem(
        name=name,
        description="测试消耗品",
        count=count,
        target_type=target_type,
    )


def _make_player_entity(
    context: Context,
    name: str,
    items: List[ConsumableItem],
    action_item: ConsumableItem,
    targets: List[str],
) -> Entity:
    """创建持有 InventoryComponent + UseConsumableItemAction 的 player 实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(InventoryComponent, name, list(items))
    entity.add(UseConsumableItemAction, name, action_item, targets)
    return entity


def _setup_mock_dungeon(mock_game: MagicMock, *, round_count: int = 1) -> None:
    """为 mock_game 配置进行中的战斗状态。"""
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
def system(mock_game: MagicMock) -> UseConsumableItemActionSystem:
    return UseConsumableItemActionSystem(mock_game)


# ---------------------------------------------------------------------------
# filter()
# ---------------------------------------------------------------------------


class TestFilter:
    def test_true_when_action_and_inventory_present(
        self, context: Context, system: UseConsumableItemActionSystem
    ) -> None:
        item = _make_consumable("治愈药水")
        entity = _make_player_entity(context, "player", [item], item, [])
        assert system.filter(entity) is True

    def test_false_when_inventory_missing(
        self, context: Context, system: UseConsumableItemActionSystem
    ) -> None:
        item = _make_consumable("治愈药水")
        entity = context.create_entity()
        entity._name = "player"
        entity.add(UseConsumableItemAction, "player", item, [])
        assert system.filter(entity) is False


# ---------------------------------------------------------------------------
# react()
# ---------------------------------------------------------------------------


class TestReact:
    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseConsumableItemActionSystem,
    ) -> None:
        mock_game.current_combat_room.combat.is_ongoing = False
        item = _make_consumable("治愈药水", count=2)
        player = _make_player_entity(context, "player", [item], item, [])

        await system.react([player])

        mock_game.broadcast_to_stage.assert_not_called()
        mock_game.resolve_stage_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcasts_notice_to_stage(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game, round_count=3)
        item = _make_consumable("鼓舞之酒", count=2)
        player = _make_player_entity(
            context, "player", [item], item, ["队友A", "队友B"]
        )
        stage = context.create_entity()
        stage._name = "测试场景"
        mock_game.resolve_stage_entity.return_value = stage

        await system.react([player])

        mock_game.broadcast_to_stage.assert_called_once()
        _, kwargs = mock_game.broadcast_to_stage.call_args
        assert kwargs["entity"] is player
        assert kwargs["exclude_entities"] == {stage}
        assert isinstance(kwargs["agent_event"], AgentEvent)
        message = kwargs["agent_event"].message
        assert "player" in message
        assert "鼓舞之酒" in message
        assert "队友A" in message
        assert "队友B" in message
        assert "3" in message

    @pytest.mark.asyncio
    async def test_broadcasts_notice_with_no_targets(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game, round_count=1)
        item = _make_consumable("治愈药水", count=1)
        player = _make_player_entity(context, "player", [item], item, [])
        stage = context.create_entity()
        stage._name = "测试场景"
        mock_game.resolve_stage_entity.return_value = stage

        await system.react([player])

        _, kwargs = mock_game.broadcast_to_stage.call_args
        assert "无" in kwargs["agent_event"].message

    @pytest.mark.asyncio
    async def test_inventory_deducted_after_react(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game)
        item = _make_consumable("治愈药水", count=2)
        player = _make_player_entity(context, "player", [item], item, [])
        mock_game.resolve_stage_entity.return_value = context.create_entity()

        await system.react([player])

        inv = player.get(InventoryComponent)
        assert inv.items[0].count == 1

    @pytest.mark.asyncio
    async def test_inventory_item_removed_when_last_count(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game)
        item = _make_consumable("最后一瓶药", count=1)
        player = _make_player_entity(context, "player", [item], item, [])
        mock_game.resolve_stage_entity.return_value = context.create_entity()

        await system.react([player])

        inv = player.get(InventoryComponent)
        assert len(inv.items) == 0

    @pytest.mark.asyncio
    async def test_still_broadcasts_when_item_not_in_inventory(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseConsumableItemActionSystem,
    ) -> None:
        """背包中找不到目标道具时仅记录警告，不影响广播通知的发送。"""
        _setup_mock_dungeon(mock_game)
        item = _make_consumable("治愈药水", count=1)
        other_item = _make_consumable("其他道具", count=1)
        player = _make_player_entity(context, "player", [other_item], item, [])
        mock_game.resolve_stage_entity.return_value = context.create_entity()

        await system.react([player])

        inv = player.get(InventoryComponent)
        assert len(inv.items) == 1
        assert inv.items[0].name == "其他道具"
        mock_game.broadcast_to_stage.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_when_multiple_entities_triggered(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game)
        item = _make_consumable("治愈药水", count=1)
        player_a = _make_player_entity(context, "player_a", [item], item, [])
        player_b = _make_player_entity(context, "player_b", [item], item, [])

        with pytest.raises(AssertionError):
            await system.react([player_a, player_b])
