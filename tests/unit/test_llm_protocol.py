"""抽象层（`ai_rpg.llm`）与绑定层（`ai_rpg.deepseek`）的契约检查。

只保留「mypy 查不出来、但改错了会静默失效」的几条：

1. 结构一致性：`DeepSeekClient` 满足 `ChatClientProtocol` / `ChatClientFactory`。
   下面 `TYPE_CHECKING` 块里的调用没有运行时行为，由 `make lint` 的 mypy 校验
   （成员缺失、property 写成可写属性、参数逆变不兼容都会当场失败）。
2. 重命名过的名字仍是同一个对象（`DeepSeekError is ChatError`），否则
   `except` 与类型标注会悄悄分叉。
3. `model=None` 仍取 provider 默认模型（工厂协议不写死模型名的代价）。
4. 绑定层 `agent_loop` 的参数表与抽象层一致（手工镜像，必须防漂移）。
5. 依赖方向：`ai_rpg.llm` 不得 import `ai_rpg.deepseek`。
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import TYPE_CHECKING, List

import ai_rpg.llm
from ai_rpg.deepseek import DeepSeekClient, DeepSeekError
from ai_rpg.llm import ChatClientFactory, ChatClientProtocol, ChatError

if TYPE_CHECKING:
    # 仅由 mypy 校验：不满足协议（成员缺失 / 参数逆变不兼容）时 lint 直接失败。
    def _accepts_client(client: ChatClientProtocol) -> None: ...
    def _accepts_factory(factory: ChatClientFactory) -> None: ...

    _accepts_client(DeepSeekClient(label="t", input_message="hi", messages=[]))
    _accepts_factory(DeepSeekClient)


def test_deepseek_error_is_chat_error() -> None:
    """实现层错误名是抽象层错误的别名（同一对象，可直接互换标注）。"""
    assert DeepSeekError is ChatError
    err = DeepSeekError("label", "boom", kind="api", status_code=429)
    assert isinstance(err, ChatError)
    assert err.retryable is True


def test_model_none_keeps_provider_default() -> None:
    """`model=None` 表示取 provider 默认模型（工厂协议与 provider 无关的代价）。"""
    client = DeepSeekClient(label="t", input_message="ping", messages=[])
    assert client._model == DeepSeekClient.MODEL_FLASH

    explicit = DeepSeekClient(
        label="t", input_message="ping", messages=[], model="x-model"
    )
    assert explicit._model == "x-model"


def test_initial_response_state() -> None:
    """协议文档承诺的初始响应态（调用 chat() 前）。"""
    client = DeepSeekClient(label="t", input_message="ping", messages=[])
    assert client.error is None
    assert client.finish_reason == ""
    assert list(client.tool_calls) == []
    assert client.usage is None
    assert client.context_usage_ratio == 0.0
    assert client.response_ai_message is None
    assert client.response_content == ""
    assert client.response_reasoning_content == ""
    assert client.dump is True


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


def test_factory_signature_matches_client_init() -> None:
    """工厂协议的形参（名字 / 顺序 / 默认值）必须与 `__init__` 对齐。"""
    init_params = inspect.signature(DeepSeekClient.__init__).parameters
    call_params = inspect.signature(ChatClientFactory.__call__).parameters

    comparable = [name for name in call_params if name != "self"]
    assert comparable == [name for name in init_params if name != "self"]
    for name in comparable:
        assert (
            call_params[name].default is init_params[name].default
        ), f"参数 {name} 的默认值不一致"


def test_deepseek_agent_loop_binding_mirrors_llm_signature() -> None:
    """绑定层手工镜像了抽象层的参数表，必须逐字一致。

    若抽象层加/改参数而绑定层没跟上，这里先失败（否则参数会被静默丢弃）。
    `create_client` 是绑定层自己注入的，不参与比较。
    """
    from ai_rpg.deepseek.agent_loop import agent_loop as bound
    from ai_rpg.llm.agent_loop import agent_loop as abstraction

    base_params = {
        name: param
        for name, param in inspect.signature(abstraction).parameters.items()
        if name != "create_client"
    }
    bound_params = inspect.signature(bound).parameters

    assert list(bound_params) == list(base_params), "参数名/顺序不一致"
    for name, param in base_params.items():
        assert bound_params[name].kind is param.kind, f"{name}: 参数种类不一致"
        assert bound_params[name].default == param.default, f"{name}: 默认值不一致"
        assert bound_params[name].annotation == param.annotation, f"{name}: 注解不一致"
