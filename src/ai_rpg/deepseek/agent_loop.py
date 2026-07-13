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
    """通用 agentic 循环：驱动 LLM 与工具交互，直到 LLM 主动 stop 或达到最大轮次。"""
    history: List[BaseMessage] = list(context)
    current_prompt = prompt

    # 进入 agent 循环，每轮与 LLM 交互，处理工具调用，直到 LLM 主动 stop 或达到最大轮次
    for round_num in range(1, max_rounds + 1):
        logger.debug(f"[agent_loop:{name}] 第 {round_num}/{max_rounds} 轮")

        # 初始化 DeepSeekClient，用于与 LLM 进行交互，传入当前轮次的 prompt、上下文、工具定义和工具选择策略
        client = DeepSeekClient(
            name=name,
            prompt=current_prompt,
            context=history,
            tools=tools,
            tool_choice=tool_choice,
        )

        # 发起 LLM 请求，捕获异常以防止整个循环崩溃
        try:
            await client.chat()
        except Exception as e:
            logger.error(
                f"[agent_loop:{name}] LLM 请求失败，第 {round_num} 轮，中止: {e}"
            )
            continue  # 继续下一轮，而不是中止整个循环

        # 检查 LLM 的 finish_reason，决定下一步动作
        if client.finish_reason == "stop":
            logger.debug(f"[agent_loop:{name}] LLM stop，第 {round_num} 轮")
            return True  # LLM 主动 stop，表示正常结束

        # 如果 finish_reason 不是 "stop" 且不是 "tool_calls"，说明出现了意外情况，记录错误并中止
        if client.finish_reason != "tool_calls" or not client.tool_calls:
            logger.error(
                f"[agent_loop:{name}] 意外的 finish_reason={client.finish_reason!r}，中止"
            )
            return False

        # 第一轮将 prompt 追加到 history，后续轮次使用 continuation 模式
        if current_prompt:
            history.append(HumanMessage(content=current_prompt))
            current_prompt = ""

        # 将 LLM 的回复消息添加到历史记录中，以便在下一轮继续使用
        ai_message = client.response_ai_message
        if ai_message is None:
            logger.error(f"[agent_loop:{name}] LLM 回复消息为空，中止")
            return False

        # 将 LLM 的回复消息添加到历史记录中，以便在下一轮继续使用
        history.append(ai_message)

        # 遍历 LLM 的工具调用列表，依次处理每个工具调用，根据工具名称找到对应的处理函数并执行，捕获异常以防止整个循环崩溃
        for tc in client.tool_calls:

            # 根据工具调用的名称找到对应的处理函数，如果找不到则记录警告并返回错误信息，否则执行处理函数并捕获异常
            handler = handlers.get(tc.function.name)
            if handler is None:
                # 如果工具调用的名称在 handlers 中找不到对应的处理函数，记录警告并返回错误信息
                logger.warning(f"[agent_loop:{name}] 未知工具: {tc.function.name!r}")
                result = f"错误：未知工具 {tc.function.name!r}"
            else:

                # 执行工具调用，传入解析后的参数，如果执行失败则记录错误并返回错误信息
                try:
                    result = handler(**json.loads(tc.function.arguments))
                except Exception as e:
                    logger.error(
                        f"[agent_loop:{name}] 工具 {tc.function.name!r} 执行失败: {e}\n"
                        f"  raw arguments: {tc.function.arguments!r}"
                    )
                    result = f"错误：工具执行失败 {e}"

            # 将工具调用的结果添加到历史记录中，以便在下一轮继续使用
            history.append(ToolMessage(content=result, tool_call_id=tc.id))

    # 如果循环结束仍未遇到 LLM stop，说明达到最大轮次限制，记录错误并中止
    logger.error(f"[agent_loop:{name}] 达到最大轮次限制 {max_rounds}，中止")
    return False
