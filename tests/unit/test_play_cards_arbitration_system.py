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
from ai_rpg.game.rpg_agent_memory import (
    KEEP_ON_COMPACT_ATTR,
    REPLACED_MESSAGES_ATTR,
)
from ai_rpg.models import (
    ActorComponent,
    AIMessage,
    Card,
    HumanMessage,
    PlayCardsAction,
    RoundEntryKind,
    RoundStatsComponent,
    SystemMessage,
    TargetType,
)
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
    # 生产环境下 stage 记忆首条是 SystemMessage，loop 从索引 1 开始。
    return SimpleNamespace(messages=[SystemMessage(content="你是本场景的仲裁者")])


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
    # 通知 / 落库阶段：角色可解析、组件齐全（HP 细节由 compute/set 的 patch 接管）
    game.get_actor_entity.return_value = MagicMock()
    game.get_entity_by_name.return_value = MagicMock()
    return game


def _patch_stats() -> Any:
    """把角色属性读写改为可控的假实现（实体本身只是 MagicMock）。

    落库逻辑已收敛到 arbitration_common，因此 patch 目标也在那里。
    """
    stats = SimpleNamespace(hp=7, max_hp=10)
    return patch.multiple(
        "ai_rpg.systems.arbitration_common",
        compute_character_stats=MagicMock(return_value=stats),
        set_character_hp=MagicMock(return_value=stats),
    )


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

        with (
            _patch_stats(),
            patch(
                "ai_rpg.systems.play_cards_arbitration_system.agent_loop",
                new=AsyncMock(side_effect=_fake_loop_success),
            ) as mock_agent_loop,
        ):
            await system._run_arbitration(actor)

        # 以 stage 为仲裁者，并携带 loop_id
        assert mock_agent_loop.await_args is not None
        assert mock_agent_loop.await_args.kwargs["name"] == "场景.测试密室"
        loop_id = mock_agent_loop.await_args.kwargs["loop_id"]
        assert loop_id.startswith("play_cards:1:角色.无名:斩击#")

        # 整段 loop 记忆被压缩为一条 HumanMessage
        assert mock_game.replace_span.call_count == 1
        _, start_index, end_index, new_messages = mock_game.replace_span.call_args.args
        assert (start_index, end_index) == (1, 3)
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

        # 落库先于压缩：HP 落库与回合记录均已发生
        latest_round = mock_game.current_dungeon_combat_room.combat.latest_round
        assert latest_round.record.call_count == 1

    @pytest.mark.asyncio
    async def test_failure_keeps_trace_and_appends_notice(
        self,
        context: Context,
        mock_game: MagicMock,
        stage_memory: SimpleNamespace,
    ) -> None:
        """失败不回滚：过程留在记忆里，只补一条系统说明。"""
        system = PlayCardsArbitrationSystem(mock_game)
        actor = _make_actor(context, "角色.无名", _make_card(), [])

        with patch(
            "ai_rpg.systems.play_cards_arbitration_system.agent_loop",
            new=AsyncMock(side_effect=_fake_loop_failure),
        ):
            await system._run_arbitration(actor)

        # 不压缩、不删除：记忆里仍是 system + 本次 loop 的两条轨迹
        mock_game.replace_span.assert_not_called()
        assert len(stage_memory.messages) == 3

        # 补一条声明「未落库」的系统说明
        mock_game.add_human_message.assert_called_once()
        notice = mock_game.add_human_message.call_args.args[1]
        assert isinstance(notice, HumanMessage)
        assert "本次结算未完成" in notice.content
        assert "play_cards:1:角色.无名:斩击#" in notice.content
        assert "未落库" in notice.content
        # 该说明在后续记忆压缩时必须原样保留
        assert getattr(notice, KEEP_ON_COMPACT_ATTR) is True
        # 说明自带 loop 起止标记：无轨迹的失败也占一个 id，可被反查
        assert getattr(notice, LOOP_ID_ATTR) == getattr(notice, LOOP_END_ATTR)

        # 回合日志留下失败痕迹（kind=failed，中性可展示文案）
        latest_round = mock_game.current_dungeon_combat_room.combat.latest_round
        assert latest_round.record.call_count == 1
        kind, log, _narrative = latest_round.record.call_args.args
        assert kind == RoundEntryKind.FAILED
        assert "play_cards:1:角色.无名:斩击#" in log
        assert "未调用 submit_arbitration" in log
        assert _narrative == "（结算未完成，本回合无变化）"

    @pytest.mark.asyncio
    async def test_exception_keeps_trace_and_appends_notice(
        self,
        context: Context,
        mock_game: MagicMock,
        stage_memory: SimpleNamespace,
    ) -> None:
        """agent_loop 抛异常同样不回滚，只把原因记进记忆。"""
        system = PlayCardsArbitrationSystem(mock_game)
        actor = _make_actor(context, "角色.无名", _make_card(), [])

        with patch(
            "ai_rpg.systems.play_cards_arbitration_system.agent_loop",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            await system._run_arbitration(actor)

        mock_game.replace_span.assert_not_called()
        notice = mock_game.add_human_message.call_args.args[1]
        assert "boom" in notice.content

    @pytest.mark.asyncio
    async def test_persistence_happens_before_compression(
        self,
        context: Context,
        mock_game: MagicMock,
        stage_memory: SimpleNamespace,
    ) -> None:
        """落库（写 HP / 回合记录）必须发生在压缩记忆之前，避免「已完成」假象。"""
        system = PlayCardsArbitrationSystem(mock_game)
        actor = _make_actor(context, "角色.无名", _make_card(), [])
        latest_round = mock_game.current_dungeon_combat_room.combat.latest_round

        order: List[str] = []
        latest_round.record.side_effect = lambda *a, **kw: order.append("record")
        mock_game.replace_span.side_effect = lambda *a, **kw: order.append(
            "replace_span"
        )

        with (
            _patch_stats(),
            patch(
                "ai_rpg.systems.play_cards_arbitration_system.agent_loop",
                new=AsyncMock(side_effect=_fake_loop_success),
            ),
        ):
            await system._run_arbitration(actor)

        assert order == ["record", "replace_span"]


class TestLoopIdUniqueness:
    @pytest.mark.asyncio
    async def test_same_actor_same_card_gets_distinct_loop_ids(
        self,
        context: Context,
        mock_game: MagicMock,
        stage_memory: SimpleNamespace,
    ) -> None:
        """同回合同角色打出同一张牌两次：loop_id 不能重号（否则反查边界会撞）。"""
        system = PlayCardsArbitrationSystem(mock_game)
        actor = _make_actor(context, "角色.无名", _make_card(), [])

        loop_ids: List[str] = []

        async def _fake_loop(**kwargs: Any) -> AgentLoopResult:
            loop_ids.append(kwargs["loop_id"])
            return _fake_loop_success(**kwargs)

        with (
            _patch_stats(),
            patch(
                "ai_rpg.systems.play_cards_arbitration_system.agent_loop",
                new=AsyncMock(side_effect=_fake_loop),
            ),
        ):
            await system._run_arbitration(actor)
            await system._run_arbitration(actor)

        assert len(loop_ids) == 2
        assert loop_ids[0] != loop_ids[1]
        assert loop_ids[0].startswith("play_cards:1:角色.无名:斩击#")

    @pytest.mark.asyncio
    async def test_repeated_failures_get_distinct_loop_ids(
        self,
        context: Context,
        mock_game: MagicMock,
        stage_memory: SimpleNamespace,
    ) -> None:
        """LLM 首轮就失败时不产生轨迹；此时仍须靠失败说明占住序号，两次失败不能重号。"""
        system = PlayCardsArbitrationSystem(mock_game)
        actor = _make_actor(context, "角色.无名", _make_card(), [])

        loop_ids: List[str] = []

        async def _fake_failing_loop(**kwargs: Any) -> AgentLoopResult:
            loop_ids.append(kwargs["loop_id"])
            return AgentLoopResult(
                success=False,
                start_index=len(kwargs["messages"]),
                end_index=len(kwargs["messages"]),
                messages=kwargs["messages"],
            )

        def _append_notice(_entity: Any, message: Any) -> None:
            stage_memory.messages.append(message)

        mock_game.add_human_message.side_effect = _append_notice

        with patch(
            "ai_rpg.systems.play_cards_arbitration_system.agent_loop",
            new=AsyncMock(side_effect=_fake_failing_loop),
        ):
            await system._run_arbitration(actor)
            await system._run_arbitration(actor)

        assert len(loop_ids) == 2
        assert loop_ids[0] != loop_ids[1]

    def test_sequence_is_derived_from_persisted_memory(self) -> None:
        """序号取自记忆里已有的 loop 起点标记：每条 CLI 命令是独立进程，进程内计数器会重号。"""
        from ai_rpg.systems.arbitration_common import make_loop_id

        empty: List[Any] = [SystemMessage(content="system")]
        assert make_loop_id(empty, "play_cards", 1, "角色.无名", "斩击") == (
            "play_cards:1:角色.无名:斩击#1"
        )

        # 模拟上一进程已压缩进记忆的两条总结（带 loop_id 起止标记）
        persisted: List[Any] = [
            SystemMessage(content="system"),
            HumanMessage(content="总结A", loop_id="play_cards:1:角色.无名:斩击#1"),
            HumanMessage(content="总结B", loop_id="artifact:1:角色.无名#2"),
        ]
        assert make_loop_id(persisted, "play_cards", 1, "角色.无名", "斩击") == (
            "play_cards:1:角色.无名:斩击#3"
        )


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
