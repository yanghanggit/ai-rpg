"""chat dump 可观测性测试。

覆盖两处开发期可观测缺口：
- get_buffer_string 默认不渲染 tool_calls，显式开启后渲染；
- _dump_chat 不再为空 prompt 追加幽灵 Human 消息，且保留本轮响应的 tool_calls。
"""

from pathlib import Path

import pytest

from ai_rpg.deepseek.client import DeepSeekClient, ToolDefinition, ToolFunction
from ai_rpg.models.messages import AIMessage, SystemMessage, get_buffer_string


def _ai_with_tool_call() -> AIMessage:
    return AIMessage(
        content="",
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_entity_stats",
                        "arguments": '{"entity_name": "角色.无名"}',
                    },
                }
            ]
        },
    )


def _dummy_tool() -> ToolDefinition:
    return ToolDefinition(
        function=ToolFunction(
            name="f", description="d", parameters={"type": "object", "properties": {}}
        )
    )


#######################################################################################################################################
# get_buffer_string
#######################################################################################################################################
def test_buffer_omits_tool_calls_by_default() -> None:
    text = get_buffer_string([_ai_with_tool_call()])
    assert "[tool_calls]" not in text
    assert "get_entity_stats" not in text


def test_buffer_renders_tool_calls_when_enabled() -> None:
    text = get_buffer_string([_ai_with_tool_call()], render_tool_calls=True)
    assert "[tool_calls]" in text
    assert "get_entity_stats" in text
    assert '{"entity_name": "角色.无名"}' in text


#######################################################################################################################################
# _dump_chat
#######################################################################################################################################
def test_dump_skips_empty_prompt_and_keeps_tool_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rpg.deepseek.client.CHAT_DUMP_DIR", tmp_path)

    # continuation 模式：prompt 为空（靠 tools 满足构造断言），历史里只有 system
    client = DeepSeekClient(
        name="场景.测试",
        prompt="",
        messages=[SystemMessage(content="SYS")],
        tools=[_dummy_tool()],
    )
    client._response_ai_message = _ai_with_tool_call()

    client._dump_chat()

    files = list(tmp_path.glob("*.txt"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")

    # 空 prompt 不应产生幽灵 Human 消息
    assert "Human" not in text
    # 本轮响应的 tool_calls 必须可见
    assert "[tool_calls]" in text
    assert "get_entity_stats" in text


def test_dump_includes_non_empty_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rpg.deepseek.client.CHAT_DUMP_DIR", tmp_path)

    client = DeepSeekClient(
        name="场景.测试",
        prompt="请描述环境",
        messages=[SystemMessage(content="SYS")],
    )
    client._response_ai_message = AIMessage(content="洞顶低矮")

    client._dump_chat()

    text = list(tmp_path.glob("*.txt"))[0].read_text(encoding="utf-8")
    assert "Human: 请描述环境" in text
    assert "洞顶低矮" in text


def test_dump_falls_back_when_response_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """响应缺失（200 但空 choices）时退化为纯文本，不抛异常。"""
    monkeypatch.setattr("ai_rpg.deepseek.client.CHAT_DUMP_DIR", tmp_path)

    client = DeepSeekClient(
        name="场景.测试",
        prompt="p",
        messages=[SystemMessage(content="SYS")],
    )
    client._response_ai_message = None

    client._dump_chat()

    text = list(tmp_path.glob("*.txt"))[0].read_text(encoding="utf-8")
    assert "AI:" in text
