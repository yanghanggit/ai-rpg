"""通用 agentic 循环工具函数。"""

import json
from typing import Callable, Dict, List, Literal, Sequence
from loguru import logger
from ..models.messages import BaseMessage, HumanMessage, ToolMessage
from .client import DeepSeekClient, ToolDefinition


async def agent_loop(
    name: str,
    prompt: str,
    context: Sequence[BaseMessage],
    tools: List[ToolDefinition],
    handlers: Dict[str, Callable[..., str]],
    max_rounds: int = 5,
    tool_choice: Literal["auto", "none", "required"] = "auto",
) -> bool:
    """通用 agentic 循环：驱动 LLM 与工具交互，直到 LLM 主动 stop 或达到最大轮次。

    工作流：
    1. 以 prompt 发起第一轮请求（附带工具定义）。
    2. 若 finish_reason == "stop" → 正常结束，返回 True。
    3. 若 finish_reason == "tool_calls" → 按名称分发工具调用，将结果追加到 history，继续下一轮。
    4. 重复直到 stop 或达到 max_rounds → 达到上限时记录错误并返回 False。

    Args:
        name: 用于日志和 DeepSeekClient 的标识名称。
        prompt: 初始任务提示词（只在第一轮发送）。
        context: 调用方的 agent 上下文（只读，内部浅拷贝）。
        tools: 提供给 LLM 的工具定义列表。
        handlers: 工具名称到处理函数的映射；处理函数接受工具参数作为关键字参数，返回结果字符串。
        max_rounds: 最大对话轮次，达到后记录错误并返回 False（兜底安全阀）。
        tool_choice: 传递给 DeepSeekClient 的工具选择策略，默认 "auto" 让 LLM 自主决定。

    Returns:
        True 表示 LLM 正常 stop；False 表示意外 finish_reason 或达到最大轮次。
    """
    history: List[BaseMessage] = list(context)
    current_prompt = prompt

    for round_num in range(1, max_rounds + 1):
        logger.debug(f"[agent_loop:{name}] 第 {round_num}/{max_rounds} 轮")
        client = DeepSeekClient(
            name=name,
            prompt=current_prompt,
            context=history,
            tools=tools,
            tool_choice=tool_choice,
        )
        await client.chat()

        if client.finish_reason == "stop":
            logger.debug(f"[agent_loop:{name}] LLM stop，第 {round_num} 轮")
            return True

        if client.finish_reason != "tool_calls" or not client.tool_calls:
            logger.error(
                f"[agent_loop:{name}] 意外的 finish_reason={client.finish_reason!r}，中止"
            )
            return False

        # 第一轮将 prompt 追加到 history，后续轮次使用 continuation 模式
        if current_prompt:
            history.append(HumanMessage(content=current_prompt))
            current_prompt = ""

        ai_message = client.response_ai_message
        if ai_message is None:
            logger.error(f"[agent_loop:{name}] LLM 回复消息为空，中止")
            return False
        history.append(ai_message)

        for tc in client.tool_calls:
            handler = handlers.get(tc.function.name)
            if handler is None:
                logger.warning(f"[agent_loop:{name}] 未知工具: {tc.function.name!r}")
                result = f"错误：未知工具 {tc.function.name!r}"
            else:
                try:
                    result = handler(**json.loads(tc.function.arguments))
                except Exception as e:
                    logger.error(
                        f"[agent_loop:{name}] 工具 {tc.function.name!r} 执行失败: {e}\n"
                        f"  raw arguments: {tc.function.arguments!r}"
                    )
                    result = f"错误：工具执行失败 {e}"
            history.append(ToolMessage(content=result, tool_call_id=tc.id))

    logger.error(f"[agent_loop:{name}] 达到最大轮次限制 {max_rounds}，中止")
    return False
