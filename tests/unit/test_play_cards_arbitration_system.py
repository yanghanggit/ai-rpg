"""PlayCardsArbitrationSystem 的 loop 记忆压缩 / 回滚行为测试。

出牌仲裁是「loop 记忆压缩」试点：成功时把本次 loop 新增的整段记忆（prompt + 工具轨迹）
替换为一条 `summary + 数据日志` 的 HumanMessage；失败时回滚删除该段。
"""

from types import SimpleNamespace
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_rpg.deepseek import LOOP_END_ATTR, LOOP_ID_ATTR, AgentLoopResult
from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.game.rpg_agent_memory import REPLACED_MESSAGES_ATTR
from ai_rpg.models import (
    ActorComponent,
    Card,
    PlayCardsAction,
    RoundStatsComponent,
    TargetType,
)
from ai_rpg.models.messages import AIMessage, HumanMessage
from ai_rpg.systems.play_cards_arbitration_system import PlayCardsArbitrationSystem


def _make_card() -> Card:
    return Card(
        name="斩击",
        description="测试卡牌",
        damage=2,
        hit_count=1,
        target_type=TargetType.SINGLE,
    )


def _make_actor(context: Context, name: str, card: Card, targets: List[str]) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "dungeon")
    entity.add(PlayCardsAction, name, card, targets)
    entity.add(RoundStatsComponent, name, 2)
    return entity


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def stage_memory() -> SimpleNamespace:
    return SimpleNamespace(messages=[])


@pytest.fixture()
def mock_game(stage_memory: SimpleNamespace) -> MagicMock:
    game = MagicMock(spec=DBGGame)
    combat = game.current_dungeon_combat_room.combat
    combat.is_ongoing = True
    combat.rounds = [object()]
    combat.latest_round.action_order = []
    combat.latest_round.completed_actors = []
    combat.latest_round.current_actor = None
    stage = MagicMock()
    stage.name = "场景.测试密室"
    game.resolve_stage_entity.return_value = stage
    game.get_agent_memory.return_value = stage_memory
    # 通知阶段故意取不到实体：压缩已完成后提前返回，避免触达 _apply 的落库分支。
    game.get_actor_entity.return_value = None
    return game


def _fake_loop_success(**kwargs: Any) -> AgentLoopResult:
    """模拟一次成功的 agent_loop：追加起止消息，并驱动 submit handler 写入 summary。"""
    messages = kwargs["messages"]
    start = len(messages)
    messages.append(
        HumanMessage(content=kwargs["input_message"], loop_id=kwargs["loop_id"])
    )
    kwargs["handlers"]["submit_arbitration"](
        combat_log="", narrative="叙事文本", summary="本次压缩总结"
    )
    messages.append(AIMessage(content="工具完成"))
    return AgentLoopResult(
        success=True,
        start_index=start,
        end_index=len(messages),
        messages=messages,
        start_message=messages[start],
    )


def _fake_loop_failure(**kwargs: Any) -> AgentLoopResult:
    messages = kwargs["messages"]
    start = len(messages)
    messages.append(
        HumanMessage(content=kwargs["input_message"], loop_id=kwargs["loop_id"])
    )
    messages.append(AIMessage(content="中途"))
    return AgentLoopResult(
        success=False,
        start_index=start,
        end_index=len(messages),
        messages=messages,
        start_message=messages[start],
    )


class TestLoopMemoryCompression:
    @pytest.mark.asyncio
    async def test_success_compresses_loop_span_into_summary(
        self,
        context: Context,
        mock_game: MagicMock,
        stage_memory: SimpleNamespace,
    ) -> None:
        system = PlayCardsArbitrationSystem(mock_game)
        actor = _make_actor(context, "角色.无名", _make_card(), [])

        with patch(
            "ai_rpg.systems.play_cards_arbitration_system.agent_loop",
            new=AsyncMock(side_effect=_fake_loop_success),
        ) as mock_agent_loop:
            await system._run_arbitration(actor)

        # 以 stage 为仲裁者，并携带 loop_id
        assert mock_agent_loop.await_args is not None
        assert mock_agent_loop.await_args.kwargs["name"] == "场景.测试密室"
        loop_id = mock_agent_loop.await_args.kwargs["loop_id"]
        assert loop_id == "play_cards:1:角色.无名:斩击"

        # 整段 loop 记忆被压缩为一条 HumanMessage
        assert mock_game.replace_span.call_count == 1
        _, start_index, end_index, new_messages = mock_game.replace_span.call_args.args
        assert (start_index, end_index) == (0, 2)
        assert (
            mock_game.replace_span.call_args.kwargs["dump_attr"]
            == REPLACED_MESSAGES_ATTR
        )
        assert len(new_messages) == 1
        summary = new_messages[0]
        assert isinstance(summary, HumanMessage)
        assert "本次压缩总结" in summary.content
        assert "本回合无 HP 变化" in summary.content
        # 总结自身带 loop_id 起终点标记，供未来反查
        assert getattr(summary, LOOP_ID_ATTR) == loop_id
        assert getattr(summary, LOOP_END_ATTR) == loop_id

    @pytest.mark.asyncio
    async def test_failure_rolls_back_loop_span(
        self,
        context: Context,
        mock_game: MagicMock,
        stage_memory: SimpleNamespace,
    ) -> None:
        system = PlayCardsArbitrationSystem(mock_game)
        actor = _make_actor(context, "角色.无名", _make_card(), [])

        with patch(
            "ai_rpg.systems.play_cards_arbitration_system.agent_loop",
            new=AsyncMock(side_effect=_fake_loop_failure),
        ):
            await system._run_arbitration(actor)

        # 失败：回滚删除 [start, end)，不写总结
        assert mock_game.replace_span.call_count == 1
        _, start_index, end_index, new_messages = mock_game.replace_span.call_args.args
        assert (start_index, end_index) == (0, 2)
        assert new_messages == []


class TestSubmitHandlerStoresSummary:
    def test_play_cards_submit_stores_summary(self) -> None:
        from ai_rpg.systems.arbitration_common import (
            ArbitrationContext,
            submit_arbitration,
        )

        ctx = ArbitrationContext()
        submit_arbitration(ctx, combat_log="", narrative="叙事", summary="总结")
        assert ctx.narrative == "叙事"
        assert ctx.summary == "总结"
