"""与具体 provider 无关的 chat completion 服务契约（Protocol）。

依赖方向
--------
    systems / llm.agent_loop / llm.batch  ──►  llm.protocol  ◄──  deepseek.client

本模块**不得** import `ai_rpg.deepseek`：抽象层不能依赖实现层。
实现方（如 `DeepSeekClient`）**不需要显式继承**本协议，靠静态结构匹配即可。

为什么只有一个成员
------------------
请求形态与响应形态都已经是值对象（`ChatCompletionRequest` / `ChatCompletionResult`），
执行者本身**没有状态**：它不再持有「这次的 prompt / 上次的响应 / 上次的错误」，
因此 service 可以被任意复用、并发调用，也不需要「调用前重置响应态」这类兜底代码。
"""

from __future__ import annotations

from typing import Protocol

from .types import ChatCompletionRequest, ChatCompletionResult


class ChatCompletionService(Protocol):
    """能完成一次 chat completion 的无状态服务（对应 ``POST /chat/completions``）。"""

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        """请求模型补全下一条 assistant 消息。

        方法名用 ``complete``（补全）而不是 ``chat``：这里没有会话状态、没有多轮
        交互，只有「给定消息历史，拿回一条补全结果」。

        约定：预期内的通讯失败（超时 / 连接 / 非 200）**不抛异常**，而是填进
        ``ChatCompletionResult.error``；真正的程序错误与取消仍然抛出，交由调用链处理。
        """
        ...


__all__ = ["ChatCompletionService"]
