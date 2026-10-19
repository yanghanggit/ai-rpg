"""chat dump 可观测性测试。

覆盖两处开发期可观测缺口：
- get_buffer_string 默认不渲染 tool_calls，显式开启后渲染；
- dump_chat 不再为空 prompt 追加幽灵 Human 消息，且保留本轮响应的 tool_calls。
"""

import importlib
from pathlib import Path

import pytest

from ai_rpg.deepseek.client import DeepSeekClient, ToolDefinition, ToolFunction
from ai_rpg.llm.chat_dump import ENV_DUMP_SWITCH, dump_chat, env_allows_dump
from ai_rpg.models import AIMessage, SystemMessage, get_buffer_string


@pytest.fixture(autouse=True)
def _isolate_dump_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个用例都清掉进程级开关，避免本地 .env / shell 环境影响断言。

    同时重置「只警告一次」的状态，让告警相关断言可重复。
    """
    monkeypatch.delenv(ENV_DUMP_SWITCH, raising=False)
    monkeypatch.setattr("ai_rpg.llm.chat_dump._warned_env_suppressed", False)


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
# dump_chat
#######################################################################################################################################
def test_dump_skips_empty_prompt_and_keeps_tool_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rpg.llm.chat_dump.CHAT_DUMP_DIR", tmp_path)

    # continuation 模式：prompt 为空（靠 tools 满足构造断言），历史里只有 system
    client = DeepSeekClient(
        label="场景.测试",
        input_message="",
        messages=[SystemMessage(content="SYS")],
        tools=[_dummy_tool()],
    )
    client._response_ai_message = _ai_with_tool_call()

    dump_chat(client)

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
    monkeypatch.setattr("ai_rpg.llm.chat_dump.CHAT_DUMP_DIR", tmp_path)

    client = DeepSeekClient(
        label="场景.测试",
        input_message="请描述环境",
        messages=[SystemMessage(content="SYS")],
    )
    client._response_ai_message = AIMessage(content="洞顶低矮")

    dump_chat(client)

    text = list(tmp_path.glob("*.txt"))[0].read_text(encoding="utf-8")
    assert "Human: 请描述环境" in text
    assert "洞顶低矮" in text


def test_dump_falls_back_when_response_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """响应缺失（200 但空 choices）时退化为纯文本，不抛异常。"""
    monkeypatch.setattr("ai_rpg.llm.chat_dump.CHAT_DUMP_DIR", tmp_path)

    client = DeepSeekClient(
        label="场景.测试",
        input_message="p",
        messages=[SystemMessage(content="SYS")],
    )
    client._response_ai_message = None

    dump_chat(client)

    text = list(tmp_path.glob("*.txt"))[0].read_text(encoding="utf-8")
    assert "AI:" in text


def test_dump_filename_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """label 里的分隔符与路径字符不能带进文件名（外观合成用 `世界|角色` 形式）。"""
    monkeypatch.setattr("ai_rpg.llm.chat_dump.CHAT_DUMP_DIR", tmp_path)

    client = DeepSeekClient(
        label="世界.外观合成|角色.无名:测试/路径",
        input_message="p",
        messages=[SystemMessage(content="SYS")],
    )
    client._response_ai_message = AIMessage(content="外观")

    dump_chat(client)

    names = [p.name for p in tmp_path.glob("*.txt")]
    assert len(names) == 1
    assert "|" not in names[0]
    assert ":" not in names[0]
    assert "/" not in names[0]
    # 中文与点号保留，便于按实体名检索
    assert "世界.外观合成_角色.无名_测试_路径" in names[0]


def test_dump_enabled_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """不传 dump 时默认落盘（开关由 client 配置承担，没有全局开关）。"""
    monkeypatch.setattr("ai_rpg.llm.chat_dump.CHAT_DUMP_DIR", tmp_path)

    client = DeepSeekClient(
        label="场景.测试",
        input_message="p",
        messages=[SystemMessage(content="SYS")],
    )
    assert client.dump is True

    client._response_ai_message = AIMessage(content="x")
    dump_chat(client)

    assert len(list(tmp_path.glob("*.txt"))) == 1


def test_dump_disabled_client_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """dump=False 的 client 直接跳过（含目录也不应被创建）。"""
    dump_dir = tmp_path / "never-created"
    monkeypatch.setattr("ai_rpg.llm.chat_dump.CHAT_DUMP_DIR", dump_dir)

    client = DeepSeekClient(
        label="场景.测试",
        input_message="p",
        messages=[SystemMessage(content="SYS")],
        dump=False,
    )
    assert client.dump is False

    client._response_ai_message = AIMessage(content="x")
    dump_chat(client)

    assert not dump_dir.exists()


############################################################################################################
# 进程级总开关（.env / 环境变量）：作为实例级 dump 的上限
############################################################################################################
@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, True),
        ("1", True),
        ("true", True),
        ("TRUE", True),
        (" yes ", True),
        ("on", True),
        ("", True),
        ("0", False),
        ("false", False),
        ("FALSE", False),
        ("no", False),
        ("off", False),
    ],
)
def test_env_switch_parsing(
    monkeypatch: pytest.MonkeyPatch, raw: "str | None", expected: bool
) -> None:
    if raw is not None:
        monkeypatch.setenv(ENV_DUMP_SWITCH, raw)
    assert env_allows_dump() is expected


def test_env_switch_off_beats_client_dump_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """总开关关闭时，client 传 dump=True 也不落盘，并只警告一次。"""
    dump_dir = tmp_path / "never-created"
    monkeypatch.setattr("ai_rpg.llm.chat_dump.CHAT_DUMP_DIR", dump_dir)
    monkeypatch.setenv(ENV_DUMP_SWITCH, "false")

    client = DeepSeekClient(
        label="场景.测试",
        input_message="p",
        messages=[SystemMessage(content="SYS")],
    )
    assert client.dump is True

    client._response_ai_message = AIMessage(content="x")
    dump_chat(client)
    dump_chat(client)

    assert not dump_dir.exists()
    # 只警告一次（避免每次 LLM 调用刷屏）
    assert importlib.import_module("ai_rpg.llm.chat_dump")._warned_env_suppressed


def test_env_switch_explicit_on_keeps_dump(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rpg.llm.chat_dump.CHAT_DUMP_DIR", tmp_path)
    monkeypatch.setenv(ENV_DUMP_SWITCH, "true")

    client = DeepSeekClient(
        label="场景.测试",
        input_message="p",
        messages=[SystemMessage(content="SYS")],
    )
    client._response_ai_message = AIMessage(content="x")

    dump_chat(client)

    assert len(list(tmp_path.glob("*.txt"))) == 1


def test_env_switch_off_and_client_dump_false_stay_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """两级都为假时不落盘，也不该产生「被总开关忽略」的告警（本来就没想开）。"""
    dump_dir = tmp_path / "never-created"
    monkeypatch.setattr("ai_rpg.llm.chat_dump.CHAT_DUMP_DIR", dump_dir)
    monkeypatch.setenv(ENV_DUMP_SWITCH, "0")

    client = DeepSeekClient(
        label="场景.测试",
        input_message="p",
        messages=[SystemMessage(content="SYS")],
        dump=False,
    )
    client._response_ai_message = AIMessage(content="x")

    dump_chat(client)

    assert not dump_dir.exists()
    assert (
        importlib.import_module("ai_rpg.llm.chat_dump")._warned_env_suppressed is False
    )
