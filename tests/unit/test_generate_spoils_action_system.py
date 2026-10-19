"""`GenerateSpoilsActionSystem` 单测：待领取队列写入后给主人一条记忆。

LLM 设计会话与原型库都在模块边界替换，只测「候选入队 + 谁被告知」这一段。
"""

import json
from typing import Any, List
from unittest.mock import MagicMock

import pytest

from ai_rpg.entitas.context import Context
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    Card,
    GenerateSpoilsAction,
    PartyMemberComponent,
    SpoilsComponent,
    TargetType,
)
from ai_rpg.systems import generate_spoils_action_system as spoils_module
from ai_rpg.systems.card_common import Candidate
from ai_rpg.systems.generate_spoils_action_system import GenerateSpoilsActionSystem


def _make_candidate(name: str) -> Candidate:
    return Candidate(
        card=Card(
            name=name,
            description="",
            cost=1,
            damage=3,
            hit_count=1,
            target_type=TargetType.SINGLE,
            source="角色.无名",
        ),
        archetype="",
        archetype_subtype="",
        summary="",
        design="",
    )


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def game(context: Context) -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.get_group.side_effect = context.get_group
    return game


async def test_spoils_fill_notifies_owner(
    context: Context, game: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """候选卡进待领取队列后，主人收到一条「待领取」记忆（不广播）。"""
    entity = context.create_entity()
    entity._name = "角色.无名"
    entity.add(ActorComponent, entity.name, "场景.河湾芦苇丛")
    entity.add(PartyMemberComponent, entity.name)
    entity.add(GenerateSpoilsAction, entity.name)

    monkeypatch.setattr(
        spoils_module, "list_card_prototype_index", lambda card_type: [{"id": 1}]
    )
    candidates: List[Candidate] = [_make_candidate("锋锐"), _make_candidate("坚守")]
    # 物化走原型库，这里只关心入队与告知，直接把候选替换成固定两张
    monkeypatch.setattr(
        GenerateSpoilsActionSystem,
        "_materialize_candidates",
        lambda self, entity, index: candidates,
    )
    monkeypatch.setattr(
        spoils_module,
        "run_card_design_session",
        lambda **kwargs: _noop(),
    )
    monkeypatch.setattr(
        spoils_module,
        "batch_run_boolean_tasks",
        lambda tasks: _results(tasks),
    )

    await GenerateSpoilsActionSystem(game).react([entity])

    spoils = entity.get(SpoilsComponent)
    assert [c.name for c in spoils.candidate_cards] == ["锋锐", "坚守"]

    message = game.add_human_message.call_args.kwargs["human_message"]
    assert "# 待领取的奖励" in message.content
    assert "「锋锐」「坚守」" in message.content
    assert json.loads(message.card_pile_change) == {
        "change": "spoils_generate",
        "deltas": {"spoils": 2},
    }


async def _noop() -> bool:
    return True


async def _results(tasks: Any) -> List[bool]:
    return [await coro for _, coro in tasks]
