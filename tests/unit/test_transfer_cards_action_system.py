"""针对 TransferCardsActionSystem（可传递卡牌从源手牌移除并 copy 到目标手牌）的单元测试。

语义约定：副本数 = 该角色在解析目标列表中的出现次数。
`SPREAD` 的列表即命中分配（一击一项、同一角色可被多击命中，只剩一个目标时全摊在它身上），
`SINGLE` / `ALL` / `SELF` 的列表里每名角色一项，故各拿一份。
"""

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


def _contents(mock_game: MagicMock) -> list[str]:
    """取出本次写出的所有记忆正文。"""
    return [
        call.kwargs["human_message"].content
        for call in mock_game.add_human_message.call_args_list
    ]


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

    async def test_repeated_targets_get_one_copy_per_hit(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        """同一角色在目标列表中出现两次 = 被命中两次 → 收到两份副本（不是一份）。"""
        source = _make_actor(context, "角色.无名")
        target = _make_actor(context, "怪物.甲")
        _stub_actor_lookup(mock_game, {"怪物.甲": target})

        card = _make_card()
        source.get(HandComponent).cards.append(card)
        source.add(PlayCardsAction, "角色.无名", card, ["怪物.甲", "怪物.甲"])

        await system.react([source])

        hand = target.get(HandComponent).cards
        assert len(hand) == 2
        # 两份必须是独立实例（各自 uuid），否则后续结算会互相串改。
        assert hand[0] is not hand[1]
        assert hand[0].uuid != hand[1].uuid
        assert all(c.transferable is False for c in hand)

    async def test_single_target_list_yields_single_copy(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        """SINGLE 的解析目标列表只有一项：`hit_count` 是多段伤害，不额外产生副本。"""
        source = _make_actor(context, "角色.无名")
        target = _make_actor(context, "怪物.甲")
        _stub_actor_lookup(mock_game, {"怪物.甲": target})

        card = _make_card()
        card.hit_count = 3  # 3 段伤害，但目标列表仍只有一项
        source.get(HandComponent).cards.append(card)
        source.add(PlayCardsAction, "角色.无名", card, ["怪物.甲"])

        await system.react([source])

        assert len(target.get(HandComponent).cards) == 1

    async def test_spread_all_hits_on_single_target_deliver_all_copies(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        """散射只剩一个目标时命中「全摊」：5 击全打中它 → 5 份副本。"""
        source = _make_actor(context, "角色.无名")
        target = _make_actor(context, "怪物.甲")
        _stub_actor_lookup(mock_game, {"怪物.甲": target})

        card = _make_card()
        card.target_type = TargetType.SPREAD
        card.hit_count = 5
        source.get(HandComponent).cards.append(card)
        source.add(
            PlayCardsAction,
            "角色.无名",
            card,
            ["怪物.甲"] * 5,  # resolve_targets 的实际产物
        )

        await system.react([source])

        assert len(target.get(HandComponent).cards) == 5

        # 接收方一条消息说明份数；传递者也看到每人几份。
        contents = _contents(mock_game)
        received = next(c for c in contents if "获得卡牌" in c)
        assert "共 5 份" in received
        outcome = next(c for c in contents if "传递卡牌" in c)
        assert "怪物.甲 5 份" in outcome

    async def test_spread_hits_split_across_characters(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        """散射分摊：甲 3 击 / 乙 2 击 → 甲 3 份、乙 2 份，总数等于击数。"""
        source = _make_actor(context, "角色.无名")
        target_a = _make_actor(context, "怪物.甲")
        target_b = _make_actor(context, "怪物.乙")
        _stub_actor_lookup(mock_game, {"怪物.甲": target_a, "怪物.乙": target_b})

        card = _make_card()
        card.target_type = TargetType.SPREAD
        card.hit_count = 5
        source.get(HandComponent).cards.append(card)
        source.add(
            PlayCardsAction,
            "角色.无名",
            card,
            ["怪物.甲", "怪物.甲", "怪物.乙", "怪物.甲", "怪物.乙"],
        )

        await system.react([source])

        assert len(target_a.get(HandComponent).cards) == 3
        assert len(target_b.get(HandComponent).cards) == 2

        outcome = next(c for c in _contents(mock_game) if "传递卡牌" in c)
        assert "怪物.甲 3 份" in outcome
        assert "怪物.乙 2 份" in outcome
        assert "共 5 份" not in outcome  # 每人份数已分别列出

    async def test_spread_including_self_uses_self_wording(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        """SPREAD 锚点为己方时解析结果可含出牌者本人，该份按「回到你自己手牌」措辞。"""
        source = _make_actor(context, "角色.无名")
        ally = _make_actor(context, "角色.队友")
        _stub_actor_lookup(mock_game, {"角色.无名": source, "角色.队友": ally})

        card = _make_card()
        card.target_type = TargetType.SPREAD
        card.hit_count = 3
        source.get(HandComponent).cards.append(card)
        source.add(
            PlayCardsAction,
            "角色.无名",
            card,
            ["角色.无名", "角色.队友", "角色.无名"],
        )

        await system.react([source])

        # 自传 2 份回自己手牌 + 队友 1 份，即命中分配本身。
        assert len(source.get(HandComponent).cards) == 2
        assert len(ally.get(HandComponent).cards) == 1

        contents = _contents(mock_game)
        received_self = next(
            c for c in contents if "获得卡牌" in c and "回到你的手牌" in c
        )
        assert "复制出 2 份副本" in received_self
        outcome = next(c for c in contents if "传递卡牌" in c)
        assert "你自己 2 份" in outcome
        assert "角色.队友 1 份" in outcome

    async def test_explicit_self_target_copies_back_to_source(
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

    async def test_each_receiver_gets_received_card_memory(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        """副本落地后必须给接收方写记忆：否则接收方手牌凭空多牌而无从解释。"""
        source = _make_actor(context, "角色.无名")
        target_a = _make_actor(context, "怪物.甲")
        target_b = _make_actor(context, "怪物.乙")
        _stub_actor_lookup(mock_game, {"怪物.甲": target_a, "怪物.乙": target_b})

        card = _make_card()
        card.block = 4
        source.get(HandComponent).cards.append(card)
        source.add(PlayCardsAction, "角色.无名", card, ["怪物.甲", "怪物.乙"])

        await system.react([source])

        # 每个接收方各一条「获得卡牌」，+ 传递者一条「传递卡牌」结果。
        assert mock_game.add_human_message.call_count == 3
        by_entity = {
            call.kwargs["entity"]: call.kwargs["human_message"]
            for call in mock_game.add_human_message.call_args_list
        }
        assert set(by_entity) == {target_a, target_b, source}

        for target in (target_a, target_b):
            message = by_entity[target]
            assert message.type == "human"
            assert "获得卡牌" in message.content
            assert "角色.无名" in message.content  # 谁给的
            assert "蚀纸毒" in message.content  # 哪张牌
            assert "共 1 份" in message.content  # 几份
            assert "不可再转手" in message.content  # 落地语义
            # 结构化附属数据：与 play_card_record 同风格，方便后续审计/压缩时定位。
            assert message.received_card is not None
            assert "蚀纸毒" in message.received_card

    async def test_giver_gets_transfer_outcome_memory(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        """传递者拿到「谁收到几份」的结果，且不代述卡牌玩法效果。"""
        source = _make_actor(context, "角色.无名")
        target_a = _make_actor(context, "怪物.甲")
        target_b = _make_actor(context, "怪物.乙")
        _stub_actor_lookup(mock_game, {"怪物.甲": target_a, "怪物.乙": target_b})

        card = _make_card()
        card.block = 4
        source.get(HandComponent).cards.append(card)
        source.add(
            PlayCardsAction, "角色.无名", card, ["怪物.甲", "怪物.甲", "怪物.乙"]
        )

        await system.react([source])

        outcome = [
            call.kwargs["human_message"].content
            for call in mock_game.add_human_message.call_args_list
            if call.kwargs["entity"] is source
        ]
        assert len(outcome) == 1
        content = outcome[0]
        assert "传递卡牌" in content
        assert "怪物.甲 2 份" in content
        assert "怪物.乙 1 份" in content
        # 本系统只管数据流转，不解释格挡/伤害等玩法效果（那属于仲裁/决策层）。
        assert "格挡" not in content
        assert "伤害" not in content

    async def test_self_transfer_memory_says_copy_returned(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        """自传递的文案要说明「副本回到你自己手牌」，不能反说成别人递给你。"""
        source = _make_actor(context, "角色.无名")
        _stub_actor_lookup(mock_game, {"角色.无名": source})

        card = _make_card()
        source.get(HandComponent).cards.append(card)
        source.add(PlayCardsAction, "角色.无名", card, ["角色.无名"])

        await system.react([source])

        contents = _contents(mock_game)
        assert len(contents) == 2
        received = next(c for c in contents if "获得卡牌" in c)
        outcome = next(c for c in contents if "传递卡牌" in c)
        assert "回到你的手牌" in received
        assert "递给了你" not in received
        assert "你自己 1 份" in outcome

    async def test_no_memory_when_nothing_transferred(
        self, context: Context, mock_game: MagicMock, system: TransferCardsActionSystem
    ) -> None:
        """战斗未进行中时不写记忆（本系统整体跳过）。"""
        mock_game.current_dungeon_combat_room.combat.is_ongoing = False
        source = _make_actor(context, "角色.无名")
        target = _make_actor(context, "怪物.甲")
        _stub_actor_lookup(mock_game, {"怪物.甲": target})

        card = _make_card()
        source.get(HandComponent).cards.append(card)
        source.add(PlayCardsAction, "角色.无名", card, ["怪物.甲"])

        await system.react([source])

        mock_game.add_human_message.assert_not_called()
