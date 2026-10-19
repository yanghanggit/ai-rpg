"""`CardOperationSystem` 单测：由牌的主人自己结算牌堆运转。

覆盖四条契约：
1. 只在牌带运转型词缀时唤起结算（没词缀不消耗 LLM）；
2. 模型调用 `copy_card` → 复制体真的进容器，并写一条 `card_pile_change`；
3. 硬上限：单次结算最多新造一张牌，牌库只读；
4. 未提交结果（loop 未完成）时牌堆不动。
"""

import json
from typing import Any, Awaitable, Callable, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    AgentMemory,
    Card,
    DeckComponent,
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    HandComponent,
    PlayCardsAction,
    SystemMessage,
    TargetType,
)
from ai_rpg.systems import card_operation_system as engine_module
from ai_rpg.systems.card_operation_system import (
    MAX_NEW_CARDS_PER_RESOLUTION,
    CardOperationSystem,
    _find_card,
)


#######################################################################################################
def _make_card(
    name: str = "怒火",
    *,
    engine_affixes: Optional[List[str]] = None,
) -> Card:
    return Card(
        name=name,
        description="那股火从握紧的地方往上爬。",
        cost=1,
        damage=2,
        hit_count=1,
        target_type=TargetType.SINGLE,
        engine_affixes=(
            engine_affixes
            if engine_affixes is not None
            else ["[engine_增殖]:打出后，在弃牌堆里再造一张这张牌自己的复制体"]
        ),
    )


def _make_actor(context: Context, name: str = "角色.无名") -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "场景.断桥头")
    entity.add(HandComponent, name, [])
    entity.add(DrawPileComponent, name, [], [])
    entity.add(DiscardPileComponent, name, [])
    entity.add(ExhaustPileComponent, name, [])
    entity.add(DeckComponent, name, [_make_card(), _make_card()])
    return entity


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def game(context: Context) -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.get_group.side_effect = context.get_group
    game.current_dungeon_combat_room.combat.is_ongoing = True
    game.current_dungeon_combat_room.combat.rounds = [MagicMock()]
    game.get_agent_memory.return_value = AgentMemory(
        name="角色.无名", messages=[SystemMessage(content="你是无名。")]
    )
    # 默认 loop 成功（用例内按需覆盖）
    game.add_human_message = MagicMock()
    return game


def _fake_loop(
    script: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Callable[..., Awaitable[bool]]:
    """伪造 agent_loop：按脚本调用 handler，模拟模型自己使用工具。"""

    async def loop(**kwargs: Any) -> bool:
        handlers: Dict[str, Any] = kwargs["handlers"]
        if script is None:
            return False  # 模拟未提交
        script(handlers)
        return True

    return loop


#######################################################################################################
class TestFilter:
    def test_plain_card_does_not_trigger(
        self, context: Context, game: MagicMock
    ) -> None:
        """没有运转型词缀的牌不唤起结算。"""
        entity = _make_actor(context)
        card = _make_card("攻击", engine_affixes=[])
        entity.get(HandComponent).cards.append(card)
        entity.add(PlayCardsAction, entity.name, card, [])

        assert not CardOperationSystem(game).filter(entity)

    def test_engine_card_triggers(self, context: Context, game: MagicMock) -> None:
        entity = _make_actor(context)
        card = _make_card()
        entity.get(HandComponent).cards.append(card)
        entity.add(PlayCardsAction, entity.name, card, [])

        assert CardOperationSystem(game).filter(entity)


#######################################################################################################
class TestCardReference:
    def test_reference_tolerates_decorated_input(
        self, context: Context, game: MagicMock
    ) -> None:
        """模型常把整行抄进参数：容器名、牌名、书名号都要能容忍。"""
        entity = _make_actor(context)
        card = _make_card()
        entity.get(DiscardPileComponent).cards.append(card)

        for ref in (
            card.uuid[:8],
            f"{card.uuid[:8]} 「怒火」",
            f"弃牌堆.{card.uuid[:8]}",
            f"discard_pile:{card.uuid[:8]}",
        ):
            pile, found = _find_card(entity, ref)
            assert pile == "discard_pile"
            assert found is card

    def test_deck_is_excluded_from_reference_resolution(
        self, context: Context, game: MagicMock
    ) -> None:
        """战斗牌是牌库副本、uuid 与牌库原牌相同：只读牌库不参与解析，否则一个引用命中两张。"""
        entity = _make_actor(context)
        card = _make_card()
        entity.get(DiscardPileComponent).cards.append(card)
        entity.get(DeckComponent).cards.append(card)  # 牌库里也有一张同 uuid 的副本

        pile, found = _find_card(entity, card.uuid[:8])
        assert pile == "discard_pile"
        assert found is card

    def test_name_fallback_when_unique(self, context: Context, game: MagicMock) -> None:
        """退化路径：模型直接给牌名，且该名字在可写牌堆里唯一时按名字定位。"""
        entity = _make_actor(context)
        card = _make_card()
        entity.get(DiscardPileComponent).cards.append(card)

        pile, found = _find_card(entity, "怒火")
        assert pile == "discard_pile"
        assert found is card


#######################################################################################################
class TestResolution:
    @pytest.mark.asyncio
    async def test_copy_card_lands_in_discard_and_is_recorded(
        self, context: Context, game: MagicMock
    ) -> None:
        """模型复制本体进弃牌堆：复制体落地（uuid 全新、词缀保留），并留一条牌堆变更记录。"""
        entity = _make_actor(context)
        card = _make_card()
        entity.get(DiscardPileComponent).cards.append(card)
        entity.add(PlayCardsAction, entity.name, card, [])

        def script(handlers: Dict[str, Any]) -> None:
            handlers["copy_card"](card.uuid[:8], "discard_pile")
            handlers["submit_card_operation"]("它烧穿了一次，又自己长回一张。")

        with patch.object(engine_module, "agent_loop", _fake_loop(script)):
            await CardOperationSystem(game).react([entity])

        discard = entity.get(DiscardPileComponent).cards
        assert len(discard) == 2
        copy = discard[-1]
        assert copy.name == card.name
        assert copy.uuid != card.uuid
        assert copy.engine_affixes == card.engine_affixes

        kwargs = game.add_human_message.call_args.kwargs
        message = kwargs["human_message"]
        assert "# 牌堆运转 · 「怒火」" in message.content
        assert json.loads(message.card_pile_change) == {
            "change": "card_operation",
            "deltas": {"discard_pile": 1},
        }

    @pytest.mark.asyncio
    async def test_copy_is_capped_per_resolution(
        self, context: Context, game: MagicMock
    ) -> None:
        """单次结算最多新造一张牌：第二次复制被拒绝，不落牌。"""
        entity = _make_actor(context)
        card = _make_card()
        entity.get(DiscardPileComponent).cards.append(card)
        entity.add(PlayCardsAction, entity.name, card, [])

        replies: List[str] = []

        def script(handlers: Dict[str, Any]) -> None:
            replies.append(handlers["copy_card"](card.uuid[:8], "discard_pile"))
            replies.append(handlers["copy_card"](card.uuid[:8], "discard_pile"))
            handlers["submit_card_operation"]("长了两次。")

        with patch.object(engine_module, "agent_loop", _fake_loop(script)):
            await CardOperationSystem(game).react([entity])

        assert (
            len(entity.get(DiscardPileComponent).cards)
            == 1 + MAX_NEW_CARDS_PER_RESOLUTION
        )
        assert "额度已用完" in replies[1]

    @pytest.mark.asyncio
    async def test_deck_is_read_only(self, context: Context, game: MagicMock) -> None:
        """牌库只读：往 deck 复制会被拒绝。"""
        entity = _make_actor(context)
        card = _make_card()
        entity.get(DiscardPileComponent).cards.append(card)
        entity.add(PlayCardsAction, entity.name, card, [])

        replies: List[str] = []

        def script(handlers: Dict[str, Any]) -> None:
            replies.append(handlers["copy_card"](card.uuid[:8], "deck"))
            handlers["submit_card_operation"]("想塞进牌库，被拒。")

        with patch.object(engine_module, "agent_loop", _fake_loop(script)):
            await CardOperationSystem(game).react([entity])

        assert "不可写入" in replies[0]
        assert len(entity.get(DeckComponent).cards) == 2

    @pytest.mark.asyncio
    async def test_unsubmitted_loop_leaves_piles_untouched(
        self, context: Context, game: MagicMock
    ) -> None:
        """loop 未提交结果：不落任何牌，也不写牌堆变更记录。"""
        entity = _make_actor(context)
        card = _make_card()
        entity.get(DiscardPileComponent).cards.append(card)
        entity.add(PlayCardsAction, entity.name, card, [])

        with patch.object(engine_module, "agent_loop", _fake_loop(None)):
            await CardOperationSystem(game).react([entity])

        assert len(entity.get(DiscardPileComponent).cards) == 1
        assert not any(
            getattr(call.kwargs.get("human_message"), "card_pile_change", None)
            for call in game.add_human_message.call_args_list
        )
