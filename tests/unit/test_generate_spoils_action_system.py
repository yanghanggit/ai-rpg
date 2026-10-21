"""`GenerateSpoilsActionSystem` 单测：待领取队列写入后给主人一条记忆；LLM 出错不写队列。

LLM 设计会话与原型库都在模块边界替换，只测「候选入队 + 谁被告知」与失败语义这一段。
"""

import json
import random
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from ai_rpg.entitas.context import Context
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    Card,
    GenerateSpoilsAction,
    MotifComponent,
    PartyMemberComponent,
    SpoilsComponent,
    TargetType,
)
from ai_rpg.systems import generate_spoils_action_system as spoils_module
from ai_rpg.systems.card_common import Candidate, DesignOutcome
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
    entity.add(GenerateSpoilsAction, entity.name, [])

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
        "read_actor_system_prompt",
        lambda game, actor_entity: "角色.无名 的设定",
    )
    # 设计会话在卡牌设计世界实体那边跑（此处只验证入队与告知，不跑真实会话）
    monkeypatch.setattr(
        spoils_module,
        "design_cards_for_actor",
        lambda *args, **kwargs: _returns(
            _outcome(
                ok=True,
                designed=len(kwargs["candidates"]),
                total=len(kwargs["candidates"]),
            )
        ),
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


async def test_spoils_injects_actor_motif(
    context: Context, game: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """角色挂载 MotifComponent 时，其 motif 作为艺术锚点传给设计会话。"""
    entity = context.create_entity()
    entity._name = "角色.坏运气"
    entity.add(ActorComponent, entity.name, "场景.河湾芦苇丛")
    entity.add(PartyMemberComponent, entity.name)
    entity.add(GenerateSpoilsAction, entity.name, [])
    entity.add(MotifComponent, entity.name, "**母题**: 差半步的时运")

    monkeypatch.setattr(
        spoils_module, "list_card_prototype_index", lambda card_type: [{"id": 1}]
    )
    candidates: List[Candidate] = [_make_candidate("锋锐")]
    monkeypatch.setattr(
        GenerateSpoilsActionSystem,
        "_materialize_candidates",
        lambda self, entity, index: candidates,
    )
    monkeypatch.setattr(
        spoils_module,
        "read_actor_system_prompt",
        lambda game, actor_entity: "角色.坏运气 的设定",
    )

    seen: Dict[str, Any] = {}

    def _fake_design(*args: Any, **kwargs: Any) -> Any:
        seen.update(kwargs)
        return _returns(_outcome(ok=True, designed=1, total=1))

    monkeypatch.setattr(spoils_module, "design_cards_for_actor", _fake_design)
    monkeypatch.setattr(
        spoils_module,
        "batch_run_boolean_tasks",
        lambda tasks: _results(tasks),
    )

    await GenerateSpoilsActionSystem(game).react([entity])

    assert seen["actor_motif"] == "**母题**: 差半步的时运"
    assert entity.has(SpoilsComponent)


async def test_spoils_without_motif_passes_empty_string(
    context: Context, game: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """未挂 MotifComponent 的角色传空串，口径与旧版本一致。"""
    entity = context.create_entity()
    entity._name = "角色.无名"
    entity.add(ActorComponent, entity.name, "场景.河湾芦苇丛")
    entity.add(PartyMemberComponent, entity.name)
    entity.add(GenerateSpoilsAction, entity.name, [])

    monkeypatch.setattr(
        spoils_module, "list_card_prototype_index", lambda card_type: [{"id": 1}]
    )
    candidates: List[Candidate] = [_make_candidate("锋锐")]
    monkeypatch.setattr(
        GenerateSpoilsActionSystem,
        "_materialize_candidates",
        lambda self, entity, index: candidates,
    )
    monkeypatch.setattr(
        spoils_module,
        "read_actor_system_prompt",
        lambda game, actor_entity: "角色.无名 的设定",
    )

    seen: Dict[str, Any] = {}

    def _fake_design(*args: Any, **kwargs: Any) -> Any:
        seen.update(kwargs)
        return _returns(_outcome(ok=True, designed=1, total=1))

    monkeypatch.setattr(spoils_module, "design_cards_for_actor", _fake_design)
    monkeypatch.setattr(
        spoils_module,
        "batch_run_boolean_tasks",
        lambda tasks: _results(tasks),
    )

    await GenerateSpoilsActionSystem(game).react([entity])

    assert seen["actor_motif"] == ""


async def test_spoils_design_failure_writes_nothing(
    context: Context, game: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LLM 设计未完成（ok=False 或未全部落地）时，不写 SpoilsComponent、不发记忆。"""
    entity = context.create_entity()
    entity._name = "角色.无名"
    entity.add(ActorComponent, entity.name, "场景.河湾芦苇丛")
    entity.add(PartyMemberComponent, entity.name)
    entity.add(GenerateSpoilsAction, entity.name, [])

    monkeypatch.setattr(
        spoils_module, "list_card_prototype_index", lambda card_type: [{"id": 1}]
    )
    candidates: List[Candidate] = [_make_candidate("锋锐"), _make_candidate("坚守")]
    monkeypatch.setattr(
        GenerateSpoilsActionSystem,
        "_materialize_candidates",
        lambda self, entity, index: candidates,
    )
    monkeypatch.setattr(
        spoils_module,
        "read_actor_system_prompt",
        lambda game, actor_entity: "角色.无名 的设定",
    )
    # 只落地一张卡：agent 提前结束，属「LLM 未完成」
    monkeypatch.setattr(
        spoils_module,
        "design_cards_for_actor",
        lambda *args, **kwargs: _returns(_outcome(ok=True, designed=1, total=2)),
    )
    monkeypatch.setattr(
        spoils_module,
        "batch_run_boolean_tasks",
        lambda tasks: _results(tasks),
    )

    await GenerateSpoilsActionSystem(game).react([entity])

    assert not entity.has(SpoilsComponent)
    game.add_human_message.assert_not_called()


async def test_spoils_agent_loop_exception_writes_nothing(
    context: Context, game: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """agent_loop 失败（ok=False）同样不写 SpoilsComponent。"""
    entity = context.create_entity()
    entity._name = "角色.无名"
    entity.add(ActorComponent, entity.name, "场景.河湾芦苇丛")
    entity.add(PartyMemberComponent, entity.name)
    entity.add(GenerateSpoilsAction, entity.name, [])

    monkeypatch.setattr(
        spoils_module, "list_card_prototype_index", lambda card_type: [{"id": 1}]
    )
    candidates: List[Candidate] = [_make_candidate("锋锐")]
    monkeypatch.setattr(
        GenerateSpoilsActionSystem,
        "_materialize_candidates",
        lambda self, entity, index: candidates,
    )
    monkeypatch.setattr(
        spoils_module,
        "read_actor_system_prompt",
        lambda game, actor_entity: "角色.无名 的设定",
    )
    monkeypatch.setattr(
        spoils_module,
        "design_cards_for_actor",
        lambda *args, **kwargs: _returns(_outcome(ok=False, designed=0, total=1)),
    )
    monkeypatch.setattr(
        spoils_module,
        "batch_run_boolean_tasks",
        lambda tasks: _results(tasks),
    )

    await GenerateSpoilsActionSystem(game).react([entity])

    assert not entity.has(SpoilsComponent)
    game.add_human_message.assert_not_called()


async def test_spoils_explicit_prototype_ids_bypass_random(
    context: Context, game: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Action 带显式候选规格时，按规格物化（顺序、重复照给），不随机抽取。"""
    entity = context.create_entity()
    entity._name = "角色.坏运气"
    entity.add(ActorComponent, entity.name, "场景.河湾芦苇丛")
    entity.add(PartyMemberComponent, entity.name)
    entity.add(
        GenerateSpoilsAction,
        entity.name,
        ["proto.summon", "proto.burst", "proto.summon"],
    )

    monkeypatch.setattr(
        spoils_module, "list_card_prototype_index", lambda card_type: [{"id": 1}]
    )
    monkeypatch.setattr(
        spoils_module,
        "design_cards_for_actor",
        lambda *args, **kwargs: _returns(
            _outcome(
                ok=True,
                designed=len(kwargs["candidates"]),
                total=len(kwargs["candidates"]),
            )
        ),
    )
    monkeypatch.setattr(
        spoils_module, "batch_run_boolean_tasks", lambda tasks: _results(tasks)
    )
    monkeypatch.setattr(
        spoils_module,
        "read_actor_system_prompt",
        lambda game, actor_entity: "角色.坏运气 的设定",
    )

    # 记录物化入参；随机路径不应被走到
    materialized_ids: List[str] = []

    def _fake_materialize(prototype_id: str, source: str) -> Candidate:
        materialized_ids.append(prototype_id)
        return _make_candidate(f"设计后的{prototype_id}#{len(materialized_ids)}")

    monkeypatch.setattr(spoils_module, "materialize_candidate", _fake_materialize)
    monkeypatch.setattr(
        random,
        "sample",
        lambda *args, **kwargs: pytest.fail("显式规格不应调用 random.sample"),
    )

    await GenerateSpoilsActionSystem(game).react([entity])

    assert materialized_ids == ["proto.summon", "proto.burst", "proto.summon"]
    spoils = entity.get(SpoilsComponent)
    assert [c.name for c in spoils.candidate_cards] == [
        "设计后的proto.summon#1",
        "设计后的proto.burst#2",
        "设计后的proto.summon#3",
    ]


async def test_spoils_explicit_prototype_failure_writes_nothing(
    context: Context, game: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """显式规格里任一原型物化失败 → 整批中止，不写 SpoilsComponent（不静默少发）。"""
    entity = context.create_entity()
    entity._name = "角色.坏运气"
    entity.add(ActorComponent, entity.name, "场景.河湾芦苇丛")
    entity.add(PartyMemberComponent, entity.name)
    entity.add(GenerateSpoilsAction, entity.name, ["proto.summon", "proto.nope"])

    monkeypatch.setattr(
        spoils_module, "list_card_prototype_index", lambda card_type: [{"id": 1}]
    )
    monkeypatch.setattr(
        spoils_module,
        "materialize_candidate",
        lambda prototype_id, source: (
            _make_candidate("余刃") if prototype_id == "proto.summon" else None
        ),
    )

    await GenerateSpoilsActionSystem(game).react([entity])

    assert not entity.has(SpoilsComponent)
    game.add_human_message.assert_not_called()


async def _returns(value: Any) -> Any:
    """把固定返回值包成协程，模拟 `design_cards_for_actor`。"""
    return value


def _outcome(*, ok: bool, designed: int, total: int) -> DesignOutcome:
    return DesignOutcome(ok=ok, designed=designed, total=total, affixes=0)


async def _results(tasks: Any) -> List[bool]:
    return [bool(await coro) for _, coro in tasks]
