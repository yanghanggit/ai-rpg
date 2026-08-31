"""agent_loop 单元测试：验证 sync / async handler 支持。"""

import json
from typing import Any
from unittest.mock import patch

import pytest

from src.ai_rpg.deepseek import ToolDefinition, ToolFunction
from src.ai_rpg.deepseek.agent_loop import agent_loop
from src.ai_rpg.deepseek.client import ToolCall
from src.ai_rpg.models.messages import AIMessage, ChatMessage


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
    with patch("src.ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.return_value = _FakeClient(ai_message, "tool_calls", [tool_call])
        ok = await agent_loop(
            name="test",
            prompt="go",
            messages=messages,
            tools=[_build_terminal_tool("my_tool")],
            handlers={"my_tool": async_handler},
            terminal_tools=[_build_terminal_tool("my_tool")],
        )

    assert ok is True
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
    with patch("src.ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.return_value = _FakeClient(ai_message, "tool_calls", [tool_call])
        ok = await agent_loop(
            name="test",
            prompt="go",
            messages=messages,
            tools=[_build_terminal_tool("my_tool")],
            handlers={"my_tool": sync_handler},
            terminal_tools=[_build_terminal_tool("my_tool")],
        )

    assert ok is True
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
    with patch("src.ai_rpg.deepseek.agent_loop.DeepSeekClient") as mock_client:
        mock_client.side_effect = [fake_bad, fake_good]
        ok = await agent_loop(
            name="test",
            prompt="go",
            messages=messages,
            tools=[submit_tool],
            handlers={"submit": submit_handler},
            terminal_tools=[submit_tool],
        )

    assert ok is True
    assert len(calls) == 1  # 坏 JSON 不调用 handler；第二轮成功调用一次
    assert messages[2].type == "tool"
    assert messages[2].content.startswith("错误：工具执行失败")
    assert messages[4].type == "tool"
    assert messages[4].content == "ok"
    assert messages[4].tool_call_id == "call_good"
