"""与具体 provider 无关的对话客户端契约（Protocol）。

依赖方向
--------
    systems / (未来的) llm.agent_loop / llm.batch  ──►  llm.protocol  ◄──  deepseek.client

本模块**不得** import `ai_rpg.deepseek`：抽象层不能依赖实现层。
实现方（如 `DeepSeekClient`）**不需要显式继承**这些 Protocol，靠静态结构匹配即可；
`@final` 与 Protocol 不冲突（final 禁止的是继承，不是结构匹配）。

为什么拆成三个协议
------------------
消费者能用到多少，就只声明多少：

- 只读结果（`_apply_result` / `_parse_loot_item` 之类）→ `ChatResponseProtocol`
- 需要发起请求（`batch_chat` / `agent_loop` / 业务直连）→ `ChatClientProtocol`
- 需要「新建 client」（`agent_loop` 每轮、各 system 的 `_build_*_client`）→ `ChatClientFactory`

刻意**不**写进协议的内容（provider 私有，写进去就等于把所有实现绑死在 DeepSeek 上）：
`MODEL_FLASH` / `MODEL_PRO` / `CONTEXT_WINDOW_TOKENS` / `get_api_key` / `get_balance` / URL 常量。
若业务确实需要「按名字选模型 / 查上下文长度」，用可选的 `ModelCatalog` 表达。

实现注意事项
------------
1. 协议成员一律写成 `@property`（只读）。若写成可写属性 `label: str`，
   mypy 会拒绝用只读 property 实现的类（cannot override writeable attribute
   with read-only property）。
2. 返回集合用 `Sequence[...]`：property 返回类型协变，`list[ToolCall]` 可匹配
   `Sequence[ToolCall]`，反之不行。
3. 默认不加 `@runtime_checkable`：带非方法成员的协议 `issubclass()` 会 TypeError，
   `isinstance()` 逐属性 getattr 也有开销；这里只需要静态检查。
"""

from __future__ import annotations

from typing import List, Optional, Protocol, Sequence

import httpx

from ..models import AIMessage, ChatMessage
from .errors import ChatError
from .types import ReasoningEffort, ToolCall, ToolChoice, ToolDefinition, Usage


############################################################################################################
class ChatResponseProtocol(Protocol):
    """一次 `chat()` 之后可读的响应视图。

    只读结果的消费者（写回组件、解析 JSON、落库留痕）只需要这一个协议。
    调用前各字段的初始值由实现方保证：`error` 为 None、`finish_reason` 为空串、
    `tool_calls` 为空列表、`usage` 为 None、`context_usage_ratio` 为 0.0。
    """

    @property
    def label(self) -> str:
        """本次请求的标签；批量场景下用于定位是哪一条。"""
        ...

    @property
    def error(self) -> Optional[ChatError]:
        """最近一次 `chat()` 的失败原因；成功或尚未调用时为 None。"""
        ...

    @property
    def response_ai_message(self) -> Optional[AIMessage]:
        """最近一次响应的 AI 消息（含 reasoning_content / tool_calls 等附属数据）。"""
        ...

    @property
    def response_content(self) -> str:
        """最近一次响应的文本内容；无响应时为空串。"""
        ...

    @property
    def response_reasoning_content(self) -> str:
        """最近一次响应的推理过程内容（thinking mode 才有）；无则为空串。"""
        ...

    @property
    def finish_reason(self) -> str:
        """最近一次响应的 finish_reason；调用 `chat()` 前为空串。"""
        ...

    @property
    def tool_calls(self) -> Sequence[ToolCall]:
        """最近一次响应中 LLM 发起的 tool 调用；无 tool call 时为空列表。"""
        ...

    @property
    def usage(self) -> Optional[Usage]:
        """最近一次响应的 token 用量；调用 `chat()` 前为 None。"""
        ...

    @property
    def context_window(self) -> int:
        """当前模型的上下文长度上限（输入 + 输出 token 总数）。"""
        ...

    @property
    def context_usage_ratio(self) -> float:
        """最近一次响应 total_tokens 占上下文长度的比例；调用前为 0.0。"""
        ...


############################################################################################################
class ChatClientProtocol(ChatResponseProtocol, Protocol):
    """可发起一次对话请求的客户端（请求态 + 响应态）。

    约定：`chat()` 返回 None，结果写入自身响应态（`response_content` /
    `finish_reason` / `tool_calls` / `usage` / `error`），失败时抛出 `ChatError`。
    """

    @property
    def input_message(self) -> str:
        """本轮新增的用户消息文本；空字符串表示 continuation 模式。"""
        ...

    @property
    def messages(self) -> Sequence[ChatMessage]:
        """本次请求随行的历史消息（只读）。"""
        ...

    @property
    def dump(self) -> bool:
        """本次请求成功后是否把完整对话落盘到 `.chat_dumps/`（调试旁路）。

        这是「实例意愿」；是否真的落盘还要通过进程级开关
        `AI_RPG_CHAT_DUMP_ENABLED`（默认开启，见 `ai_rpg.llm.chat_dump`），
        两者是 AND 关系。
        """
        ...

    async def chat(self, client: Optional[httpx.AsyncClient] = None) -> None:
        """发送一次聊天请求。

        - `client` 为 None 时由实现方自行创建临时连接；
        - 批量场景由 `batch_chat` 传入共享的 `httpx.AsyncClient` 复用连接池；
        - 每次调用开头重置响应态，失败时抛出 `ChatError` 并同时记入 `error`。
        """
        ...


############################################################################################################
class ChatClientFactory(Protocol):
    """创建 chat client 的工厂。

    Protocol 的 `__init__` 不参与结构检查（`Protocol` 只管实例成员），所以
    「构造」只能用 `__call__` 表达。类对象本身即可满足本协议。

    形参名与位置必须与实现对齐（Protocol 按参数名匹配）；因此这里把
    `label / input_message / messages` 保持为位置参数，其余为关键字参数。
    """

    def __call__(
        self,
        label: str,
        input_message: str,
        messages: Sequence[ChatMessage],
        *,
        model: Optional[str] = None,
        thinking: bool = False,
        timeout: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[Sequence[ToolDefinition]] = None,
        tool_choice: Optional[ToolChoice] = None,
        reasoning_effort: Optional[ReasoningEffort] = None,
        dump: bool = True,
    ) -> ChatClientProtocol:
        """按给定请求配置构造一个待发送的 client。"""
        ...


############################################################################################################
class ModelCatalog(Protocol):
    """可选的「模型目录」能力（provider 私有信息的通用出口）。

    不并入 `ChatClientProtocol`：DeepSeek 的 `MODEL_FLASH` / `CONTEXT_WINDOW_TOKENS`
    是 provider 私有事实，绑进主协议会让所有实现被迫编造同名常量。
    需要选型/预算的场景单独依赖本协议即可。
    """

    @property
    def default_model(self) -> str:
        """未显式指定模型时使用的默认模型 ID。"""
        ...

    def list_models(self) -> List[str]:
        """列出该 provider 当前可用的模型 ID；查询失败时返回空列表。"""
        ...

    def context_window(self, model: str) -> int:
        """给定模型的上下文长度上限（输入 + 输出 token 总数）。"""
        ...


__all__ = [
    "ChatClientFactory",
    "ChatClientProtocol",
    "ChatResponseProtocol",
    "ModelCatalog",
]
