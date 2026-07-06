"""UseConsumableItemActionSystem 单元测试。"""

from typing import List
from unittest.mock import MagicMock, patch

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    InventoryComponent,
    MonsterComponent,
    PartyMemberComponent,
    UseConsumableItemAction,
)
from src.ai_rpg.models.items import ConsumableItem
from src.ai_rpg.models.target_type import TargetType
from src.ai_rpg.systems.use_consumable_item_action_system import (
    UseConsumableItemActionSystem,
    _generate_enemy_notice,
    _generate_party_notice,
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


def _make_party_entity(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(PartyMemberComponent, name)
    return entity


def _make_monster_entity(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(MonsterComponent, name)
    return entity


def _setup_mock_dungeon(mock_game: MagicMock, *, round_count: int = 2) -> None:
    """为 mock_game 配置进行中的战斗状态。"""
    mock_game.current_dungeon.is_ongoing = True
    mock_game.current_dungeon.current_rounds = [MagicMock()] * round_count
    mock_game.current_dungeon.latest_round.consumable_use_count = 0


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
# 纯函数：_generate_party_notice / _generate_enemy_notice
# ---------------------------------------------------------------------------


class TestGeneratePartyNotice:
    def test_with_targets(self) -> None:
        item = _make_consumable("治愈药水")
        action = UseConsumableItemAction(
            name="英雄", item=item, targets=["队友A", "队友B"]
        )
        result = _generate_party_notice(action, round_number=3)
        assert "第 3 回合" in result
        assert "友方行动" in result
        assert "治愈药水" in result
        assert "队友A" in result
        assert "队友B" in result

    def test_without_targets_shows_none(self) -> None:
        item = _make_consumable("回血丹")
        action = UseConsumableItemAction(name="英雄", item=item, targets=[])
        result = _generate_party_notice(action, round_number=1)
        assert "无" in result

    def test_round_number_reflected(self) -> None:
        item = _make_consumable("X")
        action = UseConsumableItemAction(name="英雄", item=item, targets=[])
        for n in (1, 5, 10):
            assert f"第 {n} 回合" in _generate_party_notice(action, round_number=n)


class TestGenerateEnemyNotice:
    def test_with_targets(self) -> None:
        item = _make_consumable("毒雾瓶")
        action = UseConsumableItemAction(name="英雄", item=item, targets=["怪物A"])
        result = _generate_enemy_notice(action, round_number=2)
        assert "第 2 回合" in result
        assert "敌方行动" in result
        assert "毒雾瓶" in result
        assert "怪物A" in result

    def test_without_targets_shows_none(self) -> None:
        item = _make_consumable("X")
        action = UseConsumableItemAction(name="英雄", item=item, targets=[])
        result = _generate_enemy_notice(action, round_number=1)
        assert "无" in result


# ---------------------------------------------------------------------------
# _deduct_item_from_inventory
# ---------------------------------------------------------------------------


class TestDeductItemFromInventory:
    def test_count_greater_than_one_decrements(
        self, context: Context, system: UseConsumableItemActionSystem
    ) -> None:
        item = _make_consumable("治愈药水", count=3)
        entity = context.create_entity()
        entity._name = "player"
        entity.add(InventoryComponent, "player", [item])

        result = system._deduct_item_from_inventory(entity, "治愈药水")

        assert result is True
        inv = entity.get(InventoryComponent)
        assert len(inv.items) == 1
        assert inv.items[0].count == 2

    def test_count_one_removes_item(
        self, context: Context, system: UseConsumableItemActionSystem
    ) -> None:
        item = _make_consumable("治愈药水", count=1)
        entity = context.create_entity()
        entity._name = "player"
        entity.add(InventoryComponent, "player", [item])

        result = system._deduct_item_from_inventory(entity, "治愈药水")

        assert result is True
        inv = entity.get(InventoryComponent)
        assert len(inv.items) == 0

    def test_item_not_found_returns_false(
        self, context: Context, system: UseConsumableItemActionSystem
    ) -> None:
        item = _make_consumable("其他物品", count=2)
        entity = context.create_entity()
        entity._name = "player"
        entity.add(InventoryComponent, "player", [item])

        result = system._deduct_item_from_inventory(entity, "不存在的道具")

        assert result is False
        inv = entity.get(InventoryComponent)
        assert len(inv.items) == 1  # 原物品不受影响

    def test_only_first_matching_item_is_consumed(
        self, context: Context, system: UseConsumableItemActionSystem
    ) -> None:
        """背包有两条同名条目时，只消耗第一条。"""
        item_a = _make_consumable("治愈药水", count=2)
        item_b = _make_consumable("治愈药水", count=1)
        entity = context.create_entity()
        entity._name = "player"
        entity.add(InventoryComponent, "player", [item_a, item_b])

        system._deduct_item_from_inventory(entity, "治愈药水")

        inv = entity.get(InventoryComponent)
        assert len(inv.items) == 2
        assert inv.items[0].count == 1  # 第一条 -1
        assert inv.items[1].count == 1  # 第二条不变

    def test_other_items_preserved(
        self, context: Context, system: UseConsumableItemActionSystem
    ) -> None:
        potion = _make_consumable("治愈药水", count=1)
        other = _make_consumable("烟雾弹", count=5)
        entity = context.create_entity()
        entity._name = "player"
        entity.add(InventoryComponent, "player", [potion, other])

        system._deduct_item_from_inventory(entity, "治愈药水")

        inv = entity.get(InventoryComponent)
        assert len(inv.items) == 1
        assert inv.items[0].name == "烟雾弹"
        assert inv.items[0].count == 5


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
        mock_game.current_dungeon.is_ongoing = False
        item = _make_consumable("治愈药水", count=2)
        entity = _make_player_entity(context, "player", [item], item, [])

        await system.react([entity])

        mock_game.add_human_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_party_member_receives_party_notice(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game, round_count=2)

        item = _make_consumable("治愈药水", count=2)
        player = _make_player_entity(context, "player", [item], item, [])
        party_member = _make_party_entity(context, "队友A")

        with patch(
            "src.ai_rpg.systems.use_consumable_item_action_system.get_alive_actors_in_stage",
            return_value={party_member},
        ):
            await system.react([player])

        calls = mock_game.add_human_message.call_args_list
        assert len(calls) == 1
        content = calls[0].kwargs["human_message"].content
        assert "友方行动" in content
        assert "治愈药水" in content

    @pytest.mark.asyncio
    async def test_monster_receives_enemy_notice(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game, round_count=1)

        item = _make_consumable("毒雾瓶", count=1)
        player = _make_player_entity(context, "player", [item], item, ["怪物A"])
        monster = _make_monster_entity(context, "怪物A")

        with patch(
            "src.ai_rpg.systems.use_consumable_item_action_system.get_alive_actors_in_stage",
            return_value={monster},
        ):
            await system.react([player])

        calls = mock_game.add_human_message.call_args_list
        assert len(calls) == 1
        content = calls[0].kwargs["human_message"].content
        assert "敌方行动" in content
        assert "毒雾瓶" in content

    @pytest.mark.asyncio
    async def test_mixed_actors_receive_correct_notices(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseConsumableItemActionSystem,
    ) -> None:
        """场景中同时有友方和敌方时，各自收到对应阵营的通知。"""
        _setup_mock_dungeon(mock_game, round_count=3)

        item = _make_consumable("鼓舞之酒", count=2)
        player = _make_player_entity(context, "player", [item], item, ["队友A"])
        party_member = _make_party_entity(context, "队友A")
        monster = _make_monster_entity(context, "怪物X")

        with patch(
            "src.ai_rpg.systems.use_consumable_item_action_system.get_alive_actors_in_stage",
            return_value={party_member, monster},
        ):
            await system.react([player])

        calls = mock_game.add_human_message.call_args_list
        assert len(calls) == 2

        contents = [c.kwargs["human_message"].content for c in calls]
        assert any("友方行动" in c for c in contents)
        assert any("敌方行动" in c for c in contents)
        assert all("鼓舞之酒" in c for c in contents)

    @pytest.mark.asyncio
    async def test_inventory_deducted_after_react(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game, round_count=1)

        item = _make_consumable("治愈药水", count=2)
        player = _make_player_entity(context, "player", [item], item, [])

        with patch(
            "src.ai_rpg.systems.use_consumable_item_action_system.get_alive_actors_in_stage",
            return_value=set(),
        ):
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
        _setup_mock_dungeon(mock_game, round_count=1)

        item = _make_consumable("最后一瓶药", count=1)
        player = _make_player_entity(context, "player", [item], item, [])

        with patch(
            "src.ai_rpg.systems.use_consumable_item_action_system.get_alive_actors_in_stage",
            return_value=set(),
        ):
            await system.react([player])

        inv = player.get(InventoryComponent)
        assert len(inv.items) == 0

    @pytest.mark.asyncio
    async def test_round_number_in_notice_matches_current_rounds(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game, round_count=5)

        item = _make_consumable("治愈药水", count=1)
        player = _make_player_entity(context, "player", [item], item, [])
        party_member = _make_party_entity(context, "队友")

        with patch(
            "src.ai_rpg.systems.use_consumable_item_action_system.get_alive_actors_in_stage",
            return_value={party_member},
        ):
            await system.react([player])

        content = mock_game.add_human_message.call_args.kwargs["human_message"].content
        assert "第 5 回合" in content
