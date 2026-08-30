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
