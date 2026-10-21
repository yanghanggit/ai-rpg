"""`MonsterCombatDecisionSystem` 单测：决策过程被替换成「做了什么 + 原因」的一条记录。

用真实 `DBGGame`（记忆写入与 `replace_span` 都是真的），只把 LLM 与场景查询打桩：
- 推理仍按「环境+任务提示词 → 模型回包」写入，但随即被整段替换；
- 记忆里最终只剩一条决策记录，原文留在 `replaced_messages`。
"""

import json
from typing import Any, List, cast

import pytest

from ai_rpg.entitas.entity import Entity
from ai_rpg.llm import ChatCompletionRequest, ChatCompletionResult
from ai_rpg.models import (
    ActorComponent,
    AIMessage,
    Card,
    CharacterStats,
    CharacterStatsComponent,
    Combat,
    CombatRoom,
    CombatState,
    Dungeon,
    HandComponent,
    MonsterComponent,
    MonsterTurnAction,
    PartyMemberComponent,
    PassTurnAction,
    PlayCardsAction,
    Round,
    RoundStatsComponent,
    Stage,
    StageType,
    TargetType,
)
from ai_rpg.systems.combat_decision_common import REASON_MISSING
from ai_rpg.systems.monster_combat_decision_system import MonsterCombatDecisionSystem

_MODULE = "ai_rpg.systems.monster_combat_decision_system"
_STAGE_NAME = "场景.河湾芦苇丛"


#######################################################################################################
def _make_card(*, cost: int = 1, playable: bool = True) -> Card:
    return Card(
        name="攻击",
        description="",
        cost=cost,
        damage=5,
        hit_count=1,
        playable=playable,
        target_type=TargetType.SINGLE,
        source="怪物.渡口野狗",
    )


def _make_entity(game: Any, name: str, *, monster: bool) -> Entity:
    entity = cast(Entity, game._create_entity(name))
    entity.add(ActorComponent, name, _STAGE_NAME)
    entity.add(CharacterStatsComponent, name, CharacterStats(hp=10, max_hp=10))
    entity.add(HandComponent, name, [])
    if monster:
        entity.add(MonsterComponent, name)
        entity.add(RoundStatsComponent, name, 2)
        entity.add(MonsterTurnAction, name)
    else:
        entity.add(PartyMemberComponent, name)
    return entity


def _arm_combat(game: Any) -> None:
    stage = Stage(
        name=_STAGE_NAME,
        type=StageType.DUNGEON,
        profile="",
        system_message="stage",
        actors=[],
    )
    combat = Combat(name=stage.name)
    combat.state = CombatState.ONGOING
    combat.rounds = [
        Round(
            action_order=["角色.无名", "怪物.渡口野狗"],
            completed_actors=[],
            current_actor="怪物.渡口野狗",
        )
    ]
    game._world.dungeon = Dungeon(
        name="副本.断桥渡口",
        rooms=[CombatRoom(stage=stage, combat=combat)],
        profile="",
        current_room_index=0,
    )


#######################################################################################################
@pytest.fixture()
def scene(sample_game: Any) -> Any:
    game = sample_game
    _arm_combat(game)
    monster = _make_entity(game, "怪物.渡口野狗", monster=True)
    monster.get(HandComponent).cards.append(_make_card())
    opponent = _make_entity(game, "角色.无名", monster=False)
    return game, monster, opponent


async def _run(
    scene: Any,
    mp: pytest.MonkeyPatch,
    *,
    response: str,
    energy: int = 2,
    resolve_error: str = "",
) -> Any:
    """打桩后跑一次决策，返回 (game, monster)。"""
    game, monster, opponent = scene

    async def fake_batch(
        requests: List[ChatCompletionRequest],
    ) -> List[ChatCompletionResult]:
        return [
            ChatCompletionResult(
                request=request,
                ai_message=None if response == "" else AIMessage(content=response),
            )
            for request in requests
        ]

    mp.setattr(f"{_MODULE}.get_energy", lambda entity: energy)
    mp.setattr(
        f"{_MODULE}.get_alive_party_members_in_stage",
        lambda entity, game: {opponent},
    )
    mp.setattr(
        f"{_MODULE}.resolve_targets",
        lambda *args, **kwargs: (
            [] if resolve_error else [opponent.name],
            resolve_error,
        ),
    )
    mp.setattr(f"{_MODULE}.batch_complete", fake_batch)
    await MonsterCombatDecisionSystem(game).react([monster])
    return game, monster


#######################################################################################################
def _decision_messages(game: Any, monster: Entity) -> List[Any]:
    return [
        m
        for m in game.get_agent_memory(monster).messages
        if getattr(m, "combat_decision", None) is not None
    ]


class TestMonsterDecisionRecord:
    async def test_play_records_action_and_reason(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        response = json.dumps(
            {
                "pass_turn": False,
                "card_name": "攻击",
                "targets": ["角色.无名"],
                "reason": "对方没格挡，先压血线",
            }
        )
        game, monster = await _run(scene, monkeypatch, response=response)

        records = _decision_messages(game, monster)
        assert len(records) == 1
        content = records[0].content
        assert content.startswith("# 第 1 回合 · 你的行动")
        assert "你打出了「攻击」" in content
        assert "目标：角色.无名。" in content
        assert "原因：对方没格挡，先压血线" in content

        tag = json.loads(records[0].combat_decision)
        assert tag["action"] == "play"
        assert tag["targets"] == ["角色.无名"]
        assert tag["forced"] is False

        # 决策已落库
        assert monster.has(PlayCardsAction)
        assert monster.get(PlayCardsAction).targets == ["角色.无名"]

    async def test_prompt_and_raw_response_are_replaced(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """记忆里不留 prompt / 原始回包，但原文能在 replaced_messages 里反查。"""
        response = json.dumps(
            {
                "pass_turn": False,
                "card_name": "攻击",
                "targets": ["角色.无名"],
                "reason": "压血线",
            }
        )
        game, monster = await _run(scene, monkeypatch, response=response)

        messages = game.get_agent_memory(monster).messages
        assert len(messages) == 1  # 只剩决策记录
        assert "# 第 1 回合 · 出牌决策" not in messages[0].content
        replaced = messages[0].replaced_messages
        assert any("出牌决策" in str(m.get("content", "")) for m in replaced)

    async def test_pass_records_reason(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        response = json.dumps({"pass_turn": True, "reason": "能量不够，留着防守"})
        game, monster = await _run(scene, monkeypatch, response=response)

        record = _decision_messages(game, monster)[0]
        assert "你选择不出牌，直接过牌。" in record.content
        assert "原因：能量不够，留着防守" in record.content
        assert json.loads(record.combat_decision)["action"] == "pass"
        assert monster.has(PassTurnAction)

    async def test_missing_reason_uses_placeholder(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        response = json.dumps({"pass_turn": True})
        game, monster = await _run(scene, monkeypatch, response=response)

        record = _decision_messages(game, monster)[0]
        assert f"原因：{REASON_MISSING}" in record.content

    async def test_energy_shortfall_forces_pass_with_cause(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """模型想打但能量不足：记录仍写明「本想打哪张、为什么没过」并落过牌。"""
        response = json.dumps(
            {
                "pass_turn": False,
                "card_name": "攻击",
                "targets": ["角色.无名"],
                "reason": "想趁他血少收掉",
            }
        )
        game, monster = await _run(scene, monkeypatch, response=response, energy=0)

        record = _decision_messages(game, monster)[0]
        assert "你本想打出「攻击」" in record.content
        assert "当前剩余能量 0 点不足以支付费用 1" in record.content
        assert "因此过牌" in record.content
        assert "原因：想趁他血少收掉" in record.content

        tag = json.loads(record.combat_decision)
        assert tag["forced"] is True
        assert tag["action"] == "pass"
        assert monster.has(PassTurnAction)
        assert not monster.has(PlayCardsAction)

    async def test_unplayable_card_forces_pass(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        game, monster, _ = scene
        monster.get(HandComponent).cards = [_make_card(playable=False)]
        response = json.dumps(
            {"pass_turn": False, "card_name": "攻击", "targets": ["角色.无名"]}
        )
        game, monster = await _run(scene, monkeypatch, response=response)

        record = _decision_messages(game, monster)[0]
        assert "这张牌不可出牌" in record.content
        assert monster.has(PassTurnAction)

    async def test_empty_response_forces_pass_with_cause(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        game, monster = await _run(scene, monkeypatch, response="")

        record = _decision_messages(game, monster)[0]
        assert "决策没有返回任何内容" in record.content
        assert monster.has(PassTurnAction)

    async def test_target_resolution_failure_forces_pass(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        response = json.dumps(
            {"pass_turn": False, "card_name": "攻击", "targets": ["不存在"]}
        )
        game, monster = await _run(
            scene,
            monkeypatch,
            response=response,
            resolve_error="目标 '不存在' 不在存活列表中",
        )

        record = _decision_messages(game, monster)[0]
        assert "目标无法确认" in record.content
        assert monster.has(PassTurnAction)
