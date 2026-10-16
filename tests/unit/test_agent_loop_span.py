"""agent_loop 边界标记集成测试：验证 loop_id / loop_id_end 打标并可按标记反查。

通用查询语义（find_marked_span / find_marked_spans）见 test_messages_query.py。
"""

import asyncio
import json
from typing import Any
from unittest.mock import patch

import pytest

from ai_rpg.deepseek import LOOP_END_ATTR, LOOP_ID_ATTR, agent_loop
from ai_rpg.deepseek.client import ToolCall
from ai_rpg.models import (
    AIMessage,
    ChatMessage,
    SystemMessage,
    find_marked_span,
)


#######################################################################################################################################
class _FakeStopClient:
    """替身 DeepSeekClient：chat() 后立即以 stop 收尾。"""

    def __init__(self, **kwargs: Any) -> None:
        self.response_ai_message = AIMessage(content="done")
        self.finish_reason = "stop"
        self.tool_calls: list[Any] = []

    async def chat(self, client: Any = None) -> None:
        return None


#######################################################################################################################################
@pytest.mark.asyncio
async def test_agent_loop_stamps_both_boundaries_queryable_by_loop_id() -> None:
    """agent_loop 应在起点打 loop_id、末条消息打 loop_id_end，供 find_marked_span 反查。"""
    messages: list[ChatMessage] = [SystemMessage(content="sys")]
    with patch("ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.return_value = _FakeStopClient()
        result = await agent_loop(
            name="t",
            input_message="hello",
            messages=messages,
            tools=[],
            handlers={},
            loop_id="L1",
        )

    assert result.success is True
    assert getattr(messages[1], LOOP_ID_ATTR) == "L1"
    assert getattr(messages[2], LOOP_END_ATTR) == "L1"

    span = find_marked_span(messages, LOOP_ID_ATTR, "L1", end_attr=LOOP_END_ATTR)
    assert span is not None
    assert (span.start_index, span.end_index) == (1, 2)
    assert span.start_message is result.start_message
    assert span.end_message is result.rounds[-1].appended[-1]


#######################################################################################################################################
@pytest.mark.asyncio
async def test_agent_loop_without_loop_id_does_not_stamp() -> None:
    """未传 loop_id 时不打边界标记，按标记反查返回 None。"""
    messages: list[ChatMessage] = [SystemMessage(content="sys")]
    with patch("ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.return_value = _FakeStopClient()
        await agent_loop(
            name="t",
            input_message="hello",
            messages=messages,
            tools=[],
            handlers={},
        )

    assert not hasattr(messages[1], LOOP_ID_ATTR)
    assert (
        find_marked_span(messages, LOOP_ID_ATTR, "L1", end_attr=LOOP_END_ATTR) is None
    )


#######################################################################################################################################
class _FakeToolCallClient:
    """替身：chat() 后返回一次 tool_calls 响应。"""

    def __init__(self, ai_message: AIMessage, tool_calls: list[ToolCall]) -> None:
        self.response_ai_message = ai_message
        self.finish_reason = "tool_calls"
        self.tool_calls = tool_calls
        self.error: Any = None

    async def chat(self, client: Any = None) -> None:
        return None


class _FakeCancelClient:
    """替身：chat() 直接抛出 asyncio.CancelledError（BaseException，外层 except Exception 捕获不到）。"""

    def __init__(self, **kwargs: Any) -> None:
        self.error: Any = None

    async def chat(self, client: Any = None) -> None:
        raise asyncio.CancelledError()


#######################################################################################################################################
@pytest.mark.asyncio
async def test_end_marker_stamped_on_cancellation() -> None:
    """取消（BaseException）穿透前也应补打终点标记，不留悬空起点。"""
    tool_call = ToolCall(
        id="call_1",
        function=ToolCall.Function(name="my_tool", arguments=json.dumps({})),
    )
    ai_message = AIMessage(
        content="",
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "my_tool", "arguments": "{}"},
                }
            ]
        },
    )

    messages: list[ChatMessage] = [SystemMessage(content="sys")]
    with patch("ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.side_effect = [
            _FakeToolCallClient(ai_message, [tool_call]),
            _FakeCancelClient(),
        ]
        with pytest.raises(asyncio.CancelledError):
            await agent_loop(
                name="t",
                input_message="hello",
                messages=messages,
                tools=[],
                handlers={"my_tool": lambda: "ok"},
                loop_id="L1",
            )

    # 起点已打标，取消后末条（tool）补上终点标记
    assert getattr(messages[1], LOOP_ID_ATTR) == "L1"
    assert getattr(messages[-1], LOOP_END_ATTR) == "L1"
    span = find_marked_span(messages, LOOP_ID_ATTR, "L1", end_attr=LOOP_END_ATTR)
    assert span is not None
    assert (span.start_index, span.end_index) == (1, len(messages) - 1)
