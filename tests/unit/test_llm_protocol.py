"""协议层（`ai_rpg.llm`）一致性检查。

三重保证，缺一不可：

1. 静态：`TYPE_CHECKING` 块里的两处调用只由 mypy 校验（`make lint`），
   用来确认 `DeepSeekClient` 的结构确实满足 `ChatClientProtocol` / `ChatClientFactory`；
2. 运行时：协议声明的公共成员必须在实例上真的存在（防重命名漏改）；
3. 边界：抽象层不得反向 import 实现层（`ai_rpg.llm` → `ai_rpg.deepseek` 是禁止方向）。
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import TYPE_CHECKING, List

import pytest

import ai_rpg.llm
from ai_rpg.deepseek import DeepSeekClient, DeepSeekError
from ai_rpg.llm import (
    ChatClientFactory,
    ChatClientProtocol,
    ChatError,
    ChatResponseProtocol,
)

if TYPE_CHECKING:
    # 以下两行没有运行时行为，仅供 mypy 做结构一致性校验：
    # 若不满足协议（成员缺失 / property 写成可写属性 / 参数逆变不兼容），lint 直接失败。
    def _accepts_client(client: ChatClientProtocol) -> None: ...
    def _accepts_factory(factory: ChatClientFactory) -> None: ...

    _accepts_client(DeepSeekClient(label="t", input_message="hi", messages=[]))
    _accepts_factory(DeepSeekClient)


############################################################################################################
def _protocol_members(proto: type) -> List[str]:
    """取出协议自身及其协议基类声明的公共成员名（不含 dunder）。"""
    members: set[str] = set()
    for base in proto.__mro__:
        if not getattr(base, "_is_protocol", False):
            continue
        members.update(
            name
            for name in vars(base)
            if not name.startswith("_") and name not in ("register",)
        )
    return sorted(members)


############################################################################################################
@pytest.fixture
def client() -> DeepSeekClient:
    """不发请求的 DeepSeekClient 实例（仅用于结构检查）。"""
    return DeepSeekClient(label="proto-check", input_message="ping", messages=[])


############################################################################################################
def test_protocol_members_are_declared() -> None:
    """协议自身该有的成员都在（防止漏声明导致协议形同虚设）。"""
    members = _protocol_members(ChatClientProtocol)
    for expected in (
        "label",
        "error",
        "response_ai_message",
        "response_content",
        "response_reasoning_content",
        "finish_reason",
        "tool_calls",
        "usage",
        "context_window",
        "context_usage_ratio",
        "input_message",
        "messages",
        "chat",
    ):
        assert expected in members, f"ChatClientProtocol 缺少成员: {expected}"

    # 响应视图是客户端协议的子集，消费者可以只依赖它。
    assert set(_protocol_members(ChatResponseProtocol)) < set(members)


############################################################################################################
@pytest.mark.parametrize("member", _protocol_members(ChatClientProtocol))
def test_deepseek_client_exposes_protocol_member(
    client: DeepSeekClient, member: str
) -> None:
    """实现方必须暴露协议声明的全部公共成员（运行时兜底检查）。"""
    assert hasattr(client, member), f"DeepSeekClient 缺少协议成员: {member}"


############################################################################################################
def test_protocol_members_are_read_only_on_implementation(
    client: DeepSeekClient,
) -> None:
    """协议成员按 `@property` 声明，实现方也必须是只读 property 而非可写字段。

    若实现方退化成普通实例属性，协议里就无法再用 property 表达，
    会改变「响应态只由 chat() 写入」这一约束。
    """
    for member in _protocol_members(ChatResponseProtocol):
        if member == "chat":
            continue
        assert isinstance(
            getattr(DeepSeekClient, member), property
        ), f"DeepSeekClient.{member} 应为只读 property"


############################################################################################################
def test_chat_is_async(client: DeepSeekClient) -> None:
    """`chat()` 必须是协程函数（协议声明为 async）。"""
    assert inspect.iscoroutinefunction(DeepSeekClient.chat)


############################################################################################################
def test_chat_accepts_optional_shared_http_client() -> None:
    """`chat(client=...)` 的形参名与协议一致（batch_chat 依赖它复用连接池）。"""
    params = inspect.signature(DeepSeekClient.chat).parameters
    assert "client" in params
    assert params["client"].default is None


############################################################################################################
def test_deepseek_error_is_chat_error() -> None:
    """实现层错误名是抽象层错误的别名（同一对象，可直接互换标注）。"""
    assert DeepSeekError is ChatError

    err = DeepSeekError("label", "boom", kind="api", status_code=429)
    assert isinstance(err, ChatError)
    assert err.retryable is True


############################################################################################################
def test_model_optional_keeps_provider_default(client: DeepSeekClient) -> None:
    """`model=None` 表示取 provider 默认模型（工厂协议与 provider 无关的代价）。"""
    assert client._model == DeepSeekClient.MODEL_FLASH

    explicit = DeepSeekClient(
        label="proto-check", input_message="ping", messages=[], model="x-model"
    )
    assert explicit._model == "x-model"


############################################################################################################
def test_llm_layer_never_imports_provider() -> None:
    """依赖方向守卫：抽象层不得 import 实现层（只看 import 语句，不看注释）。"""
    llm_dir = Path(ai_rpg.llm.__file__).parent
    offenders: List[str] = []
    for path in sorted(llm_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules: List[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
                if node.level and path.name != "__init__.py":
                    # 相对导入的 level 在 llm 包内最多上溯一级（..models 等），
                    # 这里只需拦「上溯到 deepseek」的名字。
                    pass
                modules += [alias.name for alias in node.names]
            if any("deepseek" in module for module in modules):
                offenders.append(f"{path.name}:{getattr(node, 'lineno', 0)}")
    assert not offenders, f"ai_rpg.llm 中出现了对 provider 的 import: {offenders}"


############################################################################################################
def test_initial_response_state(client: DeepSeekClient) -> None:
    """协议文档承诺的初始响应态（调用 chat() 前）。"""
    assert client.error is None
    assert client.finish_reason == ""
    assert list(client.tool_calls) == []
    assert client.usage is None
    assert client.context_usage_ratio == 0.0
    assert client.response_ai_message is None
    assert client.response_content == ""
    assert client.response_reasoning_content == ""


############################################################################################################
def test_protocol_rejects_non_conforming_object() -> None:
    """结构类型判定的反面样例：缺成员的哑对象不应被当作 ChatResponseProtocol。

    运行时不做 isinstance（协议非 runtime_checkable），这里只验证成员枚举
    能识别出「少了哪些成员」，保证上面的兜底检查不是空转。
    """

    class _Incomplete:
        label = "x"

    missing = [
        member
        for member in _protocol_members(ChatResponseProtocol)
        if not hasattr(_Incomplete(), member)
    ]
    assert "response_content" in missing

    # 明确断言：_Incomplete 不是协议实例（避免以后误加 @runtime_checkable 改变语义）。
    with pytest.raises(TypeError):
        # 非 runtime_checkable 协议：isinstance 在运行时应直接报错，
        # 提醒我们这类检查只能交给 mypy（第 2 条保证之外不要引入运行时反射依赖）。
        isinstance(_Incomplete(), ChatResponseProtocol)  # type: ignore[misc]


############################################################################################################
def test_factory_signature_matches_client_init() -> None:
    """工厂协议的形参（名字 / 位置 / 默认值）必须与 `__init__` 对齐。"""
    init_params = inspect.signature(DeepSeekClient.__init__).parameters
    call_params = inspect.signature(ChatClientFactory.__call__).parameters

    comparable = [name for name in call_params if name != "self"]
    assert comparable == [name for name in init_params if name != "self"]

    for name in comparable:
        assert (
            call_params[name].default is init_params[name].default
        ), f"参数 {name} 的默认值不一致"
    for name in ("label", "input_message", "messages"):
        assert call_params[name].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
