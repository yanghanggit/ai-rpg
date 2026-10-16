"""针对 TransferCardsActionSystem（可传递卡牌从源手牌移除并 copy 到目标手牌）的单元测试。"""

from typing import Dict
from unittest.mock import MagicMock

import pytest

from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    Card,
    HandComponent,
    PlayCardsAction,
    TargetType,
)
from ai_rpg.systems.transfer_cards_action_system import (
    TransferCardsActionSystem,
)


def _make_card(*, transferable: bool = True) -> Card:
    return Card(
        name="蚀纸毒",
        description="测试毒牌",
        transferable=transferable,
        retain=True,
        damage=1,
        hit_count=1,
        target_type=TargetType.SINGLE,
        self_target=False,
        source="角色.无名",
    )


def _make_actor(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "stage1")
    entity.add(HandComponent, name, [])
    return entity


def _stub_actor_lookup(mock_game: MagicMock, actors: Dict[str, Entity]) -> None:
    mock_game.get_actor_entity.side_effect = lambda name: actors.get(name)


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.current_dungeon_combat_room.combat.is_ongoing = True
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> TransferCardsActionSystem:
    return TransferCardsActionSystem(mock_game)


class TestTransferCardsActionSystem:
    async def test_removes_source_card_and_copies_to_each_target(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        source = _make_actor(context, "角色.无名")
        target_a = _make_actor(context, "怪物.甲")
        target_b = _make_actor(context, "怪物.乙")
        _stub_actor_lookup(mock_game, {"怪物.甲": target_a, "怪物.乙": target_b})

        card = _make_card()
        original_uuid = card.uuid
        source.get(HandComponent).cards.append(card)
        source.add(PlayCardsAction, "角色.无名", card, ["怪物.甲", "怪物.乙"])

        await system.react([source])

        # 源手牌移除本体。
        assert card not in source.get(HandComponent).cards

        # 每个目标手牌各得到一份 copy，uuid 全新且互不相同。
        for target in (target_a, target_b):
            hand = target.get(HandComponent).cards
            assert len(hand) == 1
            copied = hand[0]
            assert copied is not card
            assert copied.uuid != original_uuid
            assert copied.name == card.name
            assert copied.source == card.source
            # 副本落地即失去传递性（不可再次传递），本体标志不变。
            assert copied.transferable is False
            assert card.transferable is True

    # async def test_skips_dead_and_missing_target_but_still_removes_source(
    #     self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    # ) -> None:
    #     source = _make_actor(context, "角色.无名")
    #     alive = _make_actor(context, "怪物.甲")
    #     dead = _make_actor(context, "怪物.乙")
    #     dead.add(DeathComponent, "怪物.乙")
    #     _stub_actor_lookup(mock_game, {"怪物.甲": alive, "怪物.乙": dead})

    #     card = _make_card()
    #     source.get(HandComponent).cards.append(card)
    #     source.add(
    #         PlayCardsAction, "角色.无名", card, ["怪物.甲", "怪物.乙", "不存在的人"]
    #     )

    #     await system.react([source])

    #     assert card not in source.get(HandComponent).cards
    #     assert len(alive.get(HandComponent).cards) == 1
    #     assert len(dead.get(HandComponent).cards) == 0

    async def test_dedups_repeated_targets(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        source = _make_actor(context, "角色.无名")
        target = _make_actor(context, "怪物.甲")
        _stub_actor_lookup(mock_game, {"怪物.甲": target})

        card = _make_card()
        source.get(HandComponent).cards.append(card)
        source.add(PlayCardsAction, "角色.无名", card, ["怪物.甲", "怪物.甲"])

        await system.react([source])

        assert card not in source.get(HandComponent).cards
        assert len(target.get(HandComponent).cards) == 1

    async def test_multi_hit_does_not_multiply_copies(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        """hit_count>1 只影响伤害段数，不增加转移副本：每个目标仍只拿一份（重复目标去重）。"""
        source = _make_actor(context, "角色.无名")
        target_a = _make_actor(context, "怪物.甲")
        target_b = _make_actor(context, "怪物.乙")
        _stub_actor_lookup(mock_game, {"怪物.甲": target_a, "怪物.乙": target_b})

        card = _make_card()
        card.hit_count = 3
        source.get(HandComponent).cards.append(card)
        source.add(PlayCardsAction, "角色.无名", card, ["怪物.甲", "怪物.甲", "怪物.乙"])

        await system.react([source])

        assert len(target_a.get(HandComponent).cards) == 1
        assert len(target_b.get(HandComponent).cards) == 1
        for target in (target_a, target_b):
            assert target.get(HandComponent).cards[0].transferable is False

    async def test_self_target_copies_back_to_source(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        """显式把自身选为目标时，自传递复制一份回源手牌。"""
        source = _make_actor(context, "角色.无名")
        _stub_actor_lookup(mock_game, {"角色.无名": source})

        card = _make_card()
        original_uuid = card.uuid
        source.get(HandComponent).cards.append(card)
        source.add(PlayCardsAction, "角色.无名", card, ["角色.无名"])

        await system.react([source])

        hand = source.get(HandComponent).cards
        assert len(hand) == 1
        copied = hand[0]
        assert copied is not card
        assert copied.uuid != original_uuid
        assert copied.source == card.source
        # 自传递拿回的副本同样失去传递性，避免「本体已进弃牌堆、副本仍可无限转手」的回收漏洞。
        assert copied.transferable is False

    async def test_received_copy_cannot_be_transferred_again(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        """链式传递被阻断：收到副本者再持牌时，filter 因 transferable=False 直接拒绝。"""
        source = _make_actor(context, "角色.无名")
        receiver = _make_actor(context, "怪物.甲")
        third = _make_actor(context, "怪物.乙")
        _stub_actor_lookup(mock_game, {"怪物.甲": receiver, "怪物.乙": third})

        card = _make_card()
        source.get(HandComponent).cards.append(card)
        source.add(PlayCardsAction, "角色.无名", card, ["怪物.甲"])
        await system.react([source])

        received = receiver.get(HandComponent).cards[0]
        assert received.transferable is False

        # 接收者将副本当作出牌动作的卡再投给第三方：此卡不再具备传递资格，系统拒绝分发。
        receiver.add(PlayCardsAction, "怪物.甲", received, ["怪物.乙"])
        assert system.filter(receiver) is False

    async def test_skips_when_not_ongoing(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        mock_game.current_dungeon_combat_room.combat.is_ongoing = False
        source = _make_actor(context, "角色.无名")
        target = _make_actor(context, "怪物.甲")
        _stub_actor_lookup(mock_game, {"怪物.甲": target})

        card = _make_card()
        source.get(HandComponent).cards.append(card)
        source.add(PlayCardsAction, "角色.无名", card, ["怪物.甲"])

        await system.react([source])

        assert card in source.get(HandComponent).cards
        assert len(target.get(HandComponent).cards) == 0

    def test_filter_rejects_non_transferable(
        self, context: Context, system: TransferCardsActionSystem
    ) -> None:
        source = _make_actor(context, "角色.无名")
        card = _make_card(transferable=False)
        source.get(HandComponent).cards.append(card)
        source.add(PlayCardsAction, "角色.无名", card, ["怪物.甲"])

        assert system.filter(source) is False

    async def test_react_rejects_non_transferable_card(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        """旁路直接调 react 时，防御性断言拦住非传递牌（正常路径由 filter 兜住）。"""
        source = _make_actor(context, "角色.无名")
        card = _make_card(transferable=False)
        source.get(HandComponent).cards.append(card)
        source.add(PlayCardsAction, "角色.无名", card, ["怪物.甲"])

        with pytest.raises(AssertionError):
            await system.react([source])
