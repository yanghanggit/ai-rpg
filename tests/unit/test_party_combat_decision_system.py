"""`PartyCombatDecisionSystem` 单测：队员的决策记录与怪物侧同构，原因用占位句。

队员的决策来自玩家（前端指令），计算端没有决策 LLM，所以本系统只写记录、不做推理：
形状对齐（做了什么 + 目标 + 原因），原因留占位——与 `home_player_plan_system` 用空 `mind`
对齐 `home_npc_plan_system` 是同一原则。
"""

import json
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from ai_rpg.entitas import GroupEvent
from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    Card,
    DeathComponent,
    HandComponent,
    MonsterComponent,
    PartyMemberComponent,
    PassTurnAction,
    PlayCardsAction,
    TargetType,
)
from ai_rpg.systems.combat_decision_common import (
    REASON_PLACEHOLDER,
    UNPLAYABLE_CAUSE,
)
from ai_rpg.systems.party_combat_decision_system import PartyCombatDecisionSystem


def _make_card() -> Card:
    return Card(
        name="攻击",
        description="",
        cost=1,
        damage=5,
        hit_count=1,
        target_type=TargetType.SINGLE,
        source="角色.无名",
    )


def _make_actor(
    context: Context, name: str, *, party: bool = True, dead: bool = False
) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "场景.河湾芦苇丛")
    entity.add(HandComponent, name, [])
    if party:
        entity.add(PartyMemberComponent, name)
    else:
        entity.add(MonsterComponent, name)
    if dead:
        entity.add(DeathComponent, name)
    return entity


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def game() -> MagicMock:
    mock = MagicMock(spec=DBGGame)
    mock.current_dungeon_combat_room.combat.is_ongoing = True
    mock.current_dungeon_combat_room.combat.rounds = [MagicMock()]
    return mock


def _records(game: MagicMock) -> List[Any]:
    return [
        call.kwargs["human_message"]
        for call in game.add_human_message.call_args_list
        if getattr(call.kwargs["human_message"], "combat_decision", None) is not None
    ]


class TestPartyDecisionRecord:
    async def test_play_writes_same_shape_as_monster(
        self, context: Context, game: MagicMock
    ) -> None:
        actor = _make_actor(context, "角色.无名")
        card = _make_card()
        actor.get(HandComponent).cards.append(card)
        actor.add(PlayCardsAction, actor.name, card, ["怪物.渡口野狗"])

        await PartyCombatDecisionSystem(game).react([actor])

        records = _records(game)
        assert len(records) == 1
        content = records[0].content
        assert content.splitlines()[0] == "# 第 1 回合 · 你的行动"
        assert "你打出了「攻击」。" in content
        assert "目标：怪物.渡口野狗。" in content
        assert f"原因：{REASON_PLACEHOLDER}" in content

        tag: Dict[str, Any] = json.loads(records[0].combat_decision)
        assert tag == {
            "round": 1,
            "action": "play",
            "card": "攻击",
            "targets": ["怪物.渡口野狗"],
            "reason": REASON_PLACEHOLDER,
            "forced": False,
        }

    async def test_pass_writes_pass_record(
        self, context: Context, game: MagicMock
    ) -> None:
        actor = _make_actor(context, "角色.无名")
        actor.add(PassTurnAction, actor.name)

        await PartyCombatDecisionSystem(game).react([actor])

        records = _records(game)
        assert len(records) == 1
        assert "你选择不出牌，直接过牌。" in records[0].content
        assert json.loads(records[0].combat_decision)["action"] == "pass"

    async def test_unplayable_card_records_blocked_play(
        self, context: Context, game: MagicMock
    ) -> None:
        """结算层会拦下不可出的牌，记录必须同步：本想打、没打出去（与怪物侧同形）。"""
        actor = _make_actor(context, "角色.无名")
        card = _make_card().model_copy(update={"playable": False})
        actor.get(HandComponent).cards.append(card)
        actor.add(PlayCardsAction, actor.name, card, ["怪物.渡口野狗"])

        await PartyCombatDecisionSystem(game).react([actor])

        records = _records(game)
        assert len(records) == 1
        content = records[0].content
        assert "你本想打出「攻击」" in content
        assert f"但{UNPLAYABLE_CAUSE}" in content
        assert "因此这次出牌没有发生" in content
        assert f"原因：{REASON_PLACEHOLDER}" in content

        tag: Dict[str, Any] = json.loads(records[0].combat_decision)
        assert tag["action"] == "pass"
        assert tag["card"] == "攻击"
        assert tag["targets"] == []
        assert tag["forced"] is True

    async def test_skips_when_combat_not_ongoing(
        self, context: Context, game: MagicMock
    ) -> None:
        game.current_dungeon_combat_room.combat.is_ongoing = False
        actor = _make_actor(context, "角色.无名")
        actor.add(PassTurnAction, actor.name)

        await PartyCombatDecisionSystem(game).react([actor])

        game.add_human_message.assert_not_called()

    def test_filter_requires_party_member_and_liveness(
        self, context: Context, game: MagicMock
    ) -> None:
        system = PartyCombatDecisionSystem(game)
        alive_party = _make_actor(context, "角色.无名")
        alive_party.add(PassTurnAction, alive_party.name)
        dead_party = _make_actor(context, "角色.坏运气", dead=True)
        dead_party.add(PassTurnAction, dead_party.name)
        monster = _make_actor(context, "怪物.渡口野狗", party=False)
        monster.add(PassTurnAction, monster.name)

        assert system.filter(alive_party)
        assert not system.filter(dead_party)
        assert not system.filter(monster)

    def test_triggers_on_both_decision_actions(
        self, context: Context, game: MagicMock
    ) -> None:
        """出牌与过牌共用同一触发集合（怪物侧两种决策都会记录）。"""
        triggers = PartyCombatDecisionSystem(game).get_trigger()
        assert len(triggers) == 2
        assert set(triggers.values()) == {GroupEvent.ADDED}
