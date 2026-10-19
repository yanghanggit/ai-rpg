"""抽象层（`ai_rpg.llm`）与绑定层（`ai_rpg.deepseek`）的契约检查。

只保留「mypy 查不出来、但改错了会静默失效」的几条：

1. 结构一致性：`DeepSeekClient` 实例满足 `ChatCompletionService`。
   下面 `TYPE_CHECKING` 块里的调用没有运行时行为，由 `make lint` 的 mypy 校验。
2. 值对象契约：`ChatCompletionRequest` 自校验 + 不可变；`ChatCompletionResult` 的派生属性正确。
3. 重命名过的名字仍是同一个对象（`DeepSeekError is ChatError`）。
4. 绑定层 `agent_loop` / `batch_complete` 的参数表与抽象层一致（手工镜像，必须防漂移）。
5. 依赖方向：`ai_rpg.llm` 不得 import `ai_rpg.deepseek`。
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
from pathlib import Path
from typing import TYPE_CHECKING, List

import pytest

import ai_rpg.llm
from ai_rpg.deepseek import DEEPSEEK_SERVICE, DeepSeekClient, DeepSeekError
from ai_rpg.llm import (
    ChatCompletionRequest,
    ChatCompletionResult,
    ChatCompletionService,
    ChatError,
)
from ai_rpg.models import AIMessage, SystemMessage

if TYPE_CHECKING:
    # 仅由 mypy 校验：不满足协议时 lint 直接失败。
    def _accepts_service(service: ChatCompletionService) -> None: ...

    _accepts_service(DEEPSEEK_SERVICE)


def _request(**kwargs: object) -> ChatCompletionRequest:
    base: dict[str, object] = {
        "label": "t",
        "input_message": "ping",
        "messages": [SystemMessage(content="sys")],
    }
    base.update(kwargs)
    return ChatCompletionRequest(**base)  # type: ignore[arg-type]


############################################################################################################
# 错误别名
############################################################################################################
def test_deepseek_error_is_chat_error() -> None:
    """实现层错误名是抽象层错误的别名（同一对象，可直接互换标注）。"""
    assert DeepSeekError is ChatError
    err = DeepSeekError("label", "boom", kind="api", status_code=429)
    assert isinstance(err, ChatError)
    assert err.retryable is True


############################################################################################################
# 值对象
############################################################################################################
class TestChatCompletionRequest:
    def test_defaults(self) -> None:
        request = _request()
        assert request.model is None
        assert request.thinking is False
        assert request.tools == ()
        assert request.tool_choice is None
        assert request.dump is True

    def test_is_immutable(self) -> None:
        request = _request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            request.label = "other"  # type: ignore[misc]

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"label": ""},
            {"input_message": ""},  # 无 tools 时 prompt 不能为空
            {"timeout": 0},
        ],
    )
    def test_rejects_invalid(self, kwargs: "dict[str, object]") -> None:
        with pytest.raises(AssertionError):
            _request(**kwargs)


class TestChatCompletionResult:
    def test_success_derived_fields(self) -> None:
        result = ChatCompletionResult(
            request=_request(),
            ai_message=AIMessage(
                content="hi", additional_kwargs={"reasoning_content": "think"}
            ),
            finish_reason="stop",
        )
        assert result.ok is True
        assert result.label == "t"
        assert result.content == "hi"
        assert result.reasoning_content == "think"

    def test_failure(self) -> None:
        result = ChatCompletionResult(
            request=_request(), error=ChatError("t", "boom", kind="timeout")
        )
        assert result.ok is False
        assert result.content == ""
        assert result.reasoning_content == ""


############################################################################################################
# provider 私有事实仍留在实现层
############################################################################################################
def test_deepseek_client_is_stateless_and_reusable() -> None:
    """service 不再持有请求/响应状态：同一实例可反复使用。"""
    assert not any(
        name in DeepSeekClient.__dict__
        for name in ("label", "input_message", "messages")
    )
    assert isinstance(DEEPSEEK_SERVICE, DeepSeekClient)


def test_context_window_lookup() -> None:
    assert DeepSeekClient.context_window(DeepSeekClient.MODEL_FLASH) > 0
    assert DeepSeekClient.context_window(None) > 0
    assert DeepSeekClient.context_window("unknown-model") > 0


############################################################################################################
# 依赖方向
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
                modules += [alias.name for alias in node.names]
            if any("deepseek" in module for module in modules):
                offenders.append(f"{path.name}:{getattr(node, 'lineno', 0)}")
    assert not offenders, f"ai_rpg.llm 中出现了对 provider 的 import: {offenders}"


############################################################################################################
# 绑定层镜像：参数表必须与抽象层一致（service 由绑定层给默认值）
############################################################################################################
def _assert_mirrors(abstraction: object, binding: object, injected: str) -> None:
    """比对参数表，忽略绑定层额外提供默认值的 `injected` 参数。"""
    base_params = {
        name: param
        for name, param in inspect.signature(abstraction).parameters.items()  # type: ignore[arg-type]
        if name != injected
    }
    bound_params = {
        name: param
        for name, param in inspect.signature(binding).parameters.items()  # type: ignore[arg-type]
        if name != injected
    }

    assert list(bound_params) == list(base_params), "参数名/顺序不一致"
    for name, param in base_params.items():
        assert bound_params[name].kind is param.kind, f"{name}: 参数种类不一致"
        assert bound_params[name].annotation == param.annotation, f"{name}: 注解不一致"
        assert bound_params[name].default == param.default, f"{name}: 默认值不一致"


def test_agent_loop_binding_mirrors_llm_signature() -> None:
    from ai_rpg.deepseek.agent_loop import agent_loop as bound
    from ai_rpg.llm.agent_loop import agent_loop as abstraction

    _assert_mirrors(abstraction, bound, injected="service")


def test_batch_complete_binding_mirrors_llm_signature() -> None:
    from ai_rpg.deepseek.batch import batch_complete as bound
    from ai_rpg.llm.batch import batch_complete as abstraction

    _assert_mirrors(abstraction, bound, injected="service")
