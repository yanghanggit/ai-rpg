"""agent_loop 单元测试：验证 sync / async handler 支持。"""

import json
from typing import Any
from unittest.mock import patch

import pytest

from ai_rpg.deepseek import ToolDefinition, ToolFunction
from ai_rpg.deepseek.agent_loop import agent_loop
from ai_rpg.deepseek.client import ToolCall
from ai_rpg.models.messages import AIMessage, ChatMessage


#######################################################################################################################################
def _build_terminal_tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        function=ToolFunction(
            name=name,
            description="测试工具",
            parameters={"type": "object", "properties": {}},
        )
    )


def _build_ai_message(name: str, arguments: dict[str, Any]) -> AIMessage:
    return AIMessage(
        content="",
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(arguments),
                    },
                }
            ]
        },
    )


class _FakeClient:
    """替身 DeepSeekClient：chat() 后暴露预设的响应。"""

    def __init__(
        self,
        ai_message: AIMessage,
        finish_reason: str,
        tool_calls: list[ToolCall],
        **kwargs: Any,
    ) -> None:
        self.response_ai_message = ai_message
        self.finish_reason = finish_reason
        self.tool_calls = tool_calls

    async def chat(self, client: Any = None) -> None:
        return None


#######################################################################################################################################
@pytest.mark.asyncio
async def test_async_handler_is_awaited_and_appended() -> None:
    calls = []

    async def async_handler(value: str) -> str:
        calls.append(value)
        return f"async:{value}"

    tool_call = ToolCall(
        id="call_1",
        function=ToolCall.Function(
            name="my_tool", arguments=json.dumps({"value": "42"})
        ),
    )
    ai_message = _build_ai_message("my_tool", {"value": "42"})

    messages: list[ChatMessage] = []
    with patch("ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.return_value = _FakeClient(ai_message, "tool_calls", [tool_call])
        ok = await agent_loop(
            name="test",
            input_message="go",
            messages=messages,
            tools=[_build_terminal_tool("my_tool")],
            handlers={"my_tool": async_handler},
            terminal_tools=[_build_terminal_tool("my_tool")],
        )

    assert ok
    assert calls == ["42"]  # async handler 确实被执行
    assert len(messages) == 3
    assert messages[0].type == "human"
    assert messages[0].content == "go"
    assert messages[1] is ai_message
    assert messages[2].type == "tool"
    assert messages[2].content == "async:42"
    assert messages[2].tool_call_id == "call_1"


#######################################################################################################################################
@pytest.mark.asyncio
async def test_sync_handler_result_appended() -> None:
    def sync_handler(value: str) -> str:
        return f"sync:{value}"

    tool_call = ToolCall(
        id="call_2",
        function=ToolCall.Function(
            name="my_tool", arguments=json.dumps({"value": "7"})
        ),
    )
    ai_message = _build_ai_message("my_tool", {"value": "7"})

    messages: list[ChatMessage] = []
    with patch("ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.return_value = _FakeClient(ai_message, "tool_calls", [tool_call])
        ok = await agent_loop(
            name="test",
            input_message="go",
            messages=messages,
            tools=[_build_terminal_tool("my_tool")],
            handlers={"my_tool": sync_handler},
            terminal_tools=[_build_terminal_tool("my_tool")],
        )

    assert ok
    assert messages[2].type == "tool"
    assert messages[2].content == "sync:7"
    assert messages[2].tool_call_id == "call_2"


#######################################################################################################################################
@pytest.mark.asyncio
async def test_failed_terminal_tool_retries_next_round() -> None:
    """终止工具的 arguments 为坏 JSON 时，不应结束循环，应回写错误并让 LLM 下一轮重试。"""
    submit_tool = _build_terminal_tool("submit")

    # 第一轮：终止工具参数是非法 JSON（模拟 LLM 漏加引号）
    bad_tool_call = ToolCall(
        id="call_bad",
        function=ToolCall.Function(name="submit", arguments='{"narrative": 未加引号}'),
    )
    fake_bad = _FakeClient(
        _build_ai_message("submit", {}), "tool_calls", [bad_tool_call]
    )

    # 第二轮：终止工具参数合法
    good_tool_call = ToolCall(
        id="call_good",
        function=ToolCall.Function(name="submit", arguments=json.dumps({})),
    )
    fake_good = _FakeClient(
        _build_ai_message("submit", {}), "tool_calls", [good_tool_call]
    )

    calls = []

    def submit_handler() -> str:
        calls.append(1)
        return "ok"

    messages: list[ChatMessage] = []
    with patch("ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.side_effect = [fake_bad, fake_good]
        ok = await agent_loop(
            name="test",
            input_message="go",
            messages=messages,
            tools=[submit_tool],
            handlers={"submit": submit_handler},
            terminal_tools=[submit_tool],
        )

    assert ok
    assert len(calls) == 1  # 坏 JSON 不调用 handler；第二轮成功调用一次
    assert messages[2].type == "tool"
    assert messages[2].content.startswith("错误：工具执行失败")
    assert messages[4].type == "tool"
    assert messages[4].content == "ok"
    assert messages[4].tool_call_id == "call_good"


#######################################################################################################################################
@pytest.mark.asyncio
async def test_stop_without_terminal_tool_is_retried_then_succeeds() -> None:
    """声明了终止工具时，LLM 直接 stop 不应视为成功；注入纠偏提示后重试直至调用终止工具。"""
    submit_tool = _build_terminal_tool("submit")

    # 第一轮：LLM 以普通文本作答并 stop，未调用终止工具
    fake_stop = _FakeClient(AIMessage(content="这就是最终结果"), "stop", [])

    # 第二轮：纠偏后正常调用终止工具
    good_tool_call = ToolCall(
        id="call_submit",
        function=ToolCall.Function(name="submit", arguments=json.dumps({})),
    )
    fake_good = _FakeClient(
        _build_ai_message("submit", {}), "tool_calls", [good_tool_call]
    )

    calls = []

    def submit_handler() -> str:
        calls.append(1)
        return "ok"

    messages: list[ChatMessage] = []
    with patch("ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.side_effect = [fake_stop, fake_good]
        ok = await agent_loop(
            name="test",
            input_message="go",
            messages=messages,
            tools=[submit_tool],
            handlers={"submit": submit_handler},
            terminal_tools=[submit_tool],
        )

    assert ok
    assert len(calls) == 1  # 终止工具最终被调用一次
    # messages: human(prompt), ai(stop), human(nudge), ai(tool_call), tool(ok)
    assert len(messages) == 5
    assert messages[2].type == "human"
    assert "终止工具" in messages[2].content
    assert messages[4].type == "tool"
    assert messages[4].content == "ok"


#######################################################################################################################################
@pytest.mark.asyncio
async def test_stop_without_terminal_tool_exhausts_retries_returns_false() -> None:
    """LLM 连续多次 stop 且始终不调用终止工具时，应返回 False 而非误报成功。"""
    submit_tool = _build_terminal_tool("submit")
    fake_stop = _FakeClient(AIMessage(content="答案"), "stop", [])

    calls = []

    def submit_handler() -> str:
        calls.append(1)
        return "ok"

    messages: list[ChatMessage] = []
    with patch("ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        # 连续 3 次 stop：第 1、2 次触发纠偏，第 3 次超过上限
        mock_client.side_effect = [fake_stop, fake_stop, fake_stop]
        ok = await agent_loop(
            name="test",
            input_message="go",
            messages=messages,
            tools=[submit_tool],
            handlers={"submit": submit_handler},
            terminal_tools=[submit_tool],
        )

    assert not ok
    assert calls == []  # 终止工具从未被调用


#######################################################################################################################################
@pytest.mark.asyncio
async def test_max_terminal_nudges_param_is_honored() -> None:
    """max_terminal_nudges 控制纠偏次数：设为 1 时，第 2 次 stop 即失败（默认 2 则尚可重试）。"""
    submit_tool = _build_terminal_tool("submit")
    fake_stop = _FakeClient(AIMessage(content="答案"), "stop", [])

    messages: list[ChatMessage] = []
    with patch("ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.side_effect = [fake_stop, fake_stop]
        ok = await agent_loop(
            name="test",
            input_message="go",
            messages=messages,
            tools=[submit_tool],
            handlers={"submit": lambda: "ok"},
            terminal_tools=[submit_tool],
            max_terminal_nudges=1,
        )

    assert not ok


#######################################################################################################################################
@pytest.mark.asyncio
async def test_stop_without_terminal_tools_returns_true() -> None:
    """未声明终止工具时，stop 仍应视为正常结束（保持原有语义）。"""
    messages: list[ChatMessage] = []
    fake_stop = _FakeClient(AIMessage(content="done"), "stop", [])
    with patch("ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.return_value = fake_stop
        ok = await agent_loop(
            name="test",
            input_message="go",
            messages=messages,
            tools=[],
            handlers={},
        )

    assert ok
    assert len(messages) == 2


#######################################################################################################################################
@pytest.mark.asyncio
async def test_result_reports_span_rounds_and_start_message() -> None:
    """返回值应能定位本次 loop 对 memory 的改动范围、起点消息与每轮过程。"""
    messages: list[ChatMessage] = []
    fake_stop = _FakeClient(AIMessage(content="done"), "stop", [])
    with patch("ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.return_value = fake_stop
        result = await agent_loop(
            name="test",
            input_message="go",
            messages=messages,
            tools=[],
            handlers={},
        )

    assert result.success is True
    assert result.start_index == 0
    assert result.end_index == 2
    assert result.start_message is messages[0]
    assert result.start_message is not None
    assert result.start_message.content == "go"
    # 单轮：human(prompt) + ai(stop)
    assert len(result.rounds) == 1
    assert result.rounds[0].client is fake_stop  # type: ignore[comparison-overlap]
    assert result.rounds[0].appended == messages[0:2]
    # bool 兼容：AgentLoopResult 成功即真
    assert bool(result) is True


#######################################################################################################################################
@pytest.mark.asyncio
async def test_input_metadata_and_loop_id_are_attached_to_start_message() -> None:
    """input_metadata 作为纯附加属性、loop_id 作为边界标记，分别外挂在起点 HumanMessage 上。"""
    messages: list[ChatMessage] = []
    fake_stop = _FakeClient(AIMessage(content="done"), "stop", [])
    with patch("ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.return_value = fake_stop
        result = await agent_loop(
            name="test",
            input_message="go",
            messages=messages,
            tools=[],
            handlers={},
            input_metadata={"custom_tag": "T"},
            loop_id="L1",
        )

    assert getattr(messages[0], "custom_tag") == "T"
    assert getattr(messages[0], "loop_id") == "L1"
    assert getattr(messages[-1], "loop_id_end") == "L1"
    assert result.start_message is not None
    assert getattr(result.start_message, "loop_id") == "L1"


#######################################################################################################################################
@pytest.mark.asyncio
async def test_result_rounds_track_each_round_appends() -> None:
    """多轮场景下 rounds 应逐轮记录该轮追加的消息（含纠偏提示）与 client。"""
    submit_tool = _build_terminal_tool("submit")
    fake_stop = _FakeClient(AIMessage(content="answer"), "stop", [])
    good_tool_call = ToolCall(
        id="call_good",
        function=ToolCall.Function(name="submit", arguments=json.dumps({})),
    )
    fake_good = _FakeClient(
        _build_ai_message("submit", {}), "tool_calls", [good_tool_call]
    )

    messages: list[ChatMessage] = []
    with patch("ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.side_effect = [fake_stop, fake_good]
        result = await agent_loop(
            name="test",
            input_message="go",
            messages=messages,
            tools=[submit_tool],
            handlers={"submit": lambda: "ok"},
            terminal_tools=[submit_tool],
        )

    assert result.success is True
    assert len(result.rounds) == 2
    assert result.rounds[0].client is fake_stop  # type: ignore[comparison-overlap]
    assert result.rounds[1].client is fake_good  # type: ignore[comparison-overlap]
    # 第 1 轮：human(prompt) + ai(stop) + human(nudge)
    assert [type(m).__name__ for m in result.rounds[0].appended] == [
        "HumanMessage",
        "AIMessage",
        "HumanMessage",
    ]
    # 第 2 轮：ai(tool_call) + tool(ok)
    assert [type(m).__name__ for m in result.rounds[1].appended] == [
        "AIMessage",
        "ToolMessage",
    ]
    assert result.start_index == 0
    assert result.end_index == len(messages) == 5
