"""`MonsterCombatDecisionSystem` 单测：工具化决策 + 决策过程被替换成「做了什么 + 原因」。

用真实 `DBGGame`（记忆写入与 `replace_span` 都是真的），只把 LLM 与场景查询打桩：
- `agent_loop` 被替换成「把脚本化的工具调用依次交给真实 handler」的假循环，
  仍按「提示词 → 模型回合 → 工具回显」写入记忆，随后被整段替换；
- 记忆里最终只剩一条决策记录，原文留在 `replaced_messages`。
"""

import json
from typing import Any, Callable, Dict, List, Optional, cast

import pytest

from ai_rpg.entitas.entity import Entity
from ai_rpg.models import (
    ActorComponent,
    AIMessage,
    Card,
    CharacterStats,
    CharacterStatsComponent,
    Combat,
    CombatRoom,
    CombatState,
    DiscardPileComponent,
    DrawPileComponent,
    Dungeon,
    ExhaustPileComponent,
    HandComponent,
    HumanMessage,
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
    ToolMessage,
)
from ai_rpg.systems.card_pile_common import PILE_EXHAUST
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
class _FakeLoopResult:
    """`AgentLoopResult` 的最小替身：只被 `bool()` 读取。"""

    def __init__(self, ok: bool) -> None:
        self._ok = ok

    def __bool__(self) -> bool:
        return self._ok


def _fake_agent_loop(
    calls: List[Dict[str, Any]],
    *,
    ok: bool = True,
    outputs: Optional[List[str]] = None,
) -> Callable[..., Any]:
    """构造假 `agent_loop`：按脚本依次调用真实 handler，并把工具回显记进 outputs。

    每个 call 可用 ``tool`` 指定要调的工具（缺省 = 终止工具，即 `submit_decision`）。
    """

    async def fake_agent_loop(
        name: str,
        input_message: str,
        messages: List[Any],
        tools: List[Any],
        handlers: Dict[str, Callable[..., str]],
        **kwargs: Any,
    ) -> _FakeLoopResult:
        # 真实 loop 也把起点提示词与模型回合追加进记忆，这里如实模拟
        messages.append(HumanMessage(content=input_message))
        default_tool = kwargs["terminal_tools"][0].function.name
        for index, scripted in enumerate(calls):
            call = dict(scripted)
            tool_name = call.pop("tool", default_tool)
            messages.append(AIMessage(content=""))
            output = handlers[tool_name](**call)
            if outputs is not None:
                outputs.append(output)
            messages.append(ToolMessage(content=output, tool_call_id=f"call_{index}"))
        return _FakeLoopResult(ok)

    return fake_agent_loop


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
    calls: List[Dict[str, Any]],
    ok: bool = True,
    energy: int = 2,
    resolve_error: str = "",
) -> Any:
    """打桩后跑一次决策，返回 (game, monster, 工具回显列表)。"""
    game, monster, opponent = scene
    outputs: List[str] = []

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
    mp.setattr(
        f"{_MODULE}.agent_loop",
        _fake_agent_loop(calls, ok=ok, outputs=outputs),
    )
    await MonsterCombatDecisionSystem(game).react([monster])
    return game, monster, outputs


def _play_call(**overrides: Any) -> Dict[str, Any]:
    call: Dict[str, Any] = {
        "pass_turn": False,
        "card_name": "攻击",
        "targets": ["角色.无名"],
        "reason": "对方没格挡，先压血线",
    }
    call.update(overrides)
    return call


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
        game, monster, outputs = await _run(scene, monkeypatch, calls=[_play_call()])

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

        # 决策已落库；工具回显确认提交成功
        assert monster.has(PlayCardsAction)
        assert monster.get(PlayCardsAction).targets == ["角色.无名"]
        assert "已提交：打出「攻击」" in outputs[0]

    async def test_tool_trace_is_replaced_by_single_record(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """记忆里不留提示词 / 工具轨迹，但原文（含工具回显）能在 replaced_messages 里反查。"""
        game, monster, _ = await _run(scene, monkeypatch, calls=[_play_call()])

        messages = game.get_agent_memory(monster).messages
        assert len(messages) == 1  # 只剩决策记录
        assert "# 第 1 回合 · 出牌决策" not in messages[0].content
        replaced = messages[0].replaced_messages
        dumped = " ".join(str(m.get("content", "")) for m in replaced)
        assert "出牌决策" in dumped  # 提示词
        assert "已提交：打出「攻击」" in dumped  # 工具回显

    async def test_pass_records_reason(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        game, monster, _ = await _run(
            scene,
            monkeypatch,
            calls=[{"pass_turn": True, "reason": "能量不够，留着防守"}],
        )

        record = _decision_messages(game, monster)[0]
        assert "你选择不出牌，直接过牌。" in record.content
        assert "原因：能量不够，留着防守" in record.content
        assert json.loads(record.combat_decision)["action"] == "pass"
        assert monster.has(PassTurnAction)

    async def test_missing_reason_uses_placeholder(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        game, monster, _ = await _run(scene, monkeypatch, calls=[{"pass_turn": True}])

        record = _decision_messages(game, monster)[0]
        assert f"原因：{REASON_MISSING}" in record.content


class TestReadPilesTool:
    async def test_read_piles_reports_every_pile(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`read_piles` 给出四个牌堆的只读快照（牌名 + 费用），不影响后续决策。"""
        game, monster, _ = scene
        name = monster.name
        monster.add(DrawPileComponent, name, [_make_card()], [_make_card()])
        monster.add(DiscardPileComponent, name, [_make_card()])
        monster.add(ExhaustPileComponent, name, [])

        game, monster, outputs = await _run(
            scene, monkeypatch, calls=[{"tool": "read_piles"}, _play_call()]
        )

        report = outputs[0]
        assert report.startswith("# 你的牌堆")
        assert "抽牌堆（1 张，先抽最前" in report
        assert "弃牌堆（1 张）" in report
        assert "消耗堆（0 张）：（空）" in report
        assert "保留队列（1 张，下次抽牌先回手）" in report
        assert "「攻击」(费1)" in report

        # 只读：牌堆未变，决策照常落库
        assert len(monster.get(DrawPileComponent).cards) == 1
        assert len(monster.get(DrawPileComponent).retained_cards) == 1
        assert monster.has(PlayCardsAction)

    async def test_read_piles_can_target_one_pile_and_rejects_unknown(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        game, monster, _ = scene
        monster.add(ExhaustPileComponent, monster.name, [])

        game, monster, outputs = await _run(
            scene,
            monkeypatch,
            calls=[
                {"tool": "read_piles", "pile": PILE_EXHAUST},
                {"tool": "read_piles", "pile": "deck"},
                _play_call(),
            ],
        )

        assert outputs[0] == "# 你的牌堆\n消耗堆（0 张）：（空）"
        assert "错误：未知牌堆" in outputs[1]
        assert monster.has(PlayCardsAction)


class TestToolLoopSelfCorrection:
    async def test_energy_shortfall_is_reported_and_model_self_corrects(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """能量不足不再直接把行动作废：工具回错，模型可改判过牌（记录为自主过牌）。"""
        game, monster, outputs = await _run(
            scene,
            monkeypatch,
            calls=[_play_call(), {"pass_turn": True, "reason": "打不出去，先蓄着"}],
            energy=0,
        )

        assert "不足以支付费用 1" in outputs[0]
        record = _decision_messages(game, monster)[0]
        assert "你选择不出牌，直接过牌。" in record.content
        assert "原因：打不出去，先蓄着" in record.content
        assert json.loads(record.combat_decision)["forced"] is False
        assert monster.has(PassTurnAction)

    async def test_never_submitted_falls_back_to_forced_pass(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """始终提交不出可执行结果（loop 未收敛）：记录「本想打哪张、为何没打成」并落过牌。"""
        game, monster, outputs = await _run(
            scene, monkeypatch, calls=[_play_call()], ok=False, energy=0
        )

        assert "不足以支付费用 1" in outputs[0]
        record = _decision_messages(game, monster)[0]
        assert "你本想打出「攻击」" in record.content
        assert "当前剩余能量 0 点不足以支付费用 1" in record.content
        assert "因此过牌" in record.content

        tag = json.loads(record.combat_decision)
        assert tag["forced"] is True
        assert tag["action"] == "pass"
        assert monster.has(PassTurnAction)
        assert not monster.has(PlayCardsAction)

    async def test_unplayable_card_is_rejected(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        game, monster, _ = scene
        monster.get(HandComponent).cards = [_make_card(playable=False)]

        game, monster, outputs = await _run(
            scene, monkeypatch, calls=[_play_call()], ok=False
        )

        assert "这张牌不可出牌" in outputs[0]
        record = _decision_messages(game, monster)[0]
        assert "这张牌不可出牌" in record.content
        assert monster.has(PassTurnAction)

    async def test_unknown_card_name_is_rejected(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        game, monster, outputs = await _run(
            scene, monkeypatch, calls=[_play_call(card_name="不存在的牌")], ok=False
        )

        assert "不在你的手牌中" in outputs[0]
        record = _decision_messages(game, monster)[0]
        assert "你本想打出「不存在的牌」" in record.content
        assert monster.has(PassTurnAction)

    async def test_target_resolution_failure_is_rejected(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        game, monster, outputs = await _run(
            scene,
            monkeypatch,
            calls=[_play_call(targets=["不存在"])],
            ok=False,
            resolve_error="目标 '不存在' 不在存活列表中",
        )

        assert "目标无法确认" in outputs[0]
        record = _decision_messages(game, monster)[0]
        assert "目标无法确认" in record.content
        assert monster.has(PassTurnAction)

    async def test_loop_failure_without_any_attempt(
        self, scene: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """一次工具都没提交就失败（LLM 无响应 / 轮次耗尽）：兜底过牌且说明原因。"""
        game, monster, _ = await _run(scene, monkeypatch, calls=[], ok=False)

        record = _decision_messages(game, monster)[0]
        assert "决策没有返回可执行的结果" in record.content
        assert json.loads(record.combat_decision)["forced"] is True
        assert monster.has(PassTurnAction)
