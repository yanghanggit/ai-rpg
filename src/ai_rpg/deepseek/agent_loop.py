"""通用 agentic 循环工具函数。"""

import inspect
import json
from typing import Awaitable, Callable, Dict, List, Literal, Optional, Union

from loguru import logger

from ..models.messages import ChatMessage, HumanMessage, ToolMessage
from .client import DeepSeekClient, ToolDefinition


def _build_terminal_nudge(terminal_tools: List[ToolDefinition]) -> str:
    """构建「未调用终止工具即停止」时的纠偏提示。"""
    names = "、".join(t.function.name for t in terminal_tools)
    return (
        f"你尚未调用要求的终止工具（{names}）就结束了回复。"
        "请勿以普通文本直接作答，必须通过工具调用提交最终结果；"
        "如仍需读取或写入数据，请先完成相应工具调用，最后再调用终止工具提交。"
    )


async def agent_loop(
    name: str,
    prompt: str,
    messages: List[ChatMessage],
    tools: List[ToolDefinition],
    handlers: Dict[str, Callable[..., Union[str, Awaitable[str]]]],
    max_rounds: int = 5,
    max_terminal_nudges: int = 2,
    tool_choice: Literal["auto", "none", "required"] = "auto",
    thinking: bool = False,
    terminal_tools: List[ToolDefinition] = [],
) -> bool:
    """通用 agentic 循环：驱动 LLM 与工具交互，直到 LLM 主动 stop、调用 terminal_tools 中任一或达到最大轮次。

    当声明了 terminal_tools 时，`finish_reason == "stop"` 不再等同于正常结束：
    若尚未成功调用任一终止工具，则视为未完成，注入纠偏提示后强制重试（最多
    `max_terminal_nudges` 次），避免 LLM 把结果当作普通文本输出而丢失结算。
    """
    # 方案 C：不复制 messages，直接原地追加，由调用方决定是否传入副本以隔离。
    history: List[ChatMessage] = messages
    current_prompt = prompt
    terminal_tool_names = {t.function.name for t in terminal_tools}
    nudge_count = 0

    # 进入 agent 循环，每轮与 LLM 交互，处理工具调用，直到 LLM 主动 stop 或达到最大轮次
    for round_num in range(1, max_rounds + 1):
        logger.debug(f"[agent_loop:{name}] 第 {round_num}/{max_rounds} 轮")

        # 初始化 DeepSeekClient，用于与 LLM 进行交互，传入当前轮次的 prompt、消息历史、工具定义和工具选择策略。
        # 纠偏重试轮强制 tool_choice="required"，逼迫 LLM 通过工具调用而非普通文本作答。
        client = DeepSeekClient(
            name=name,
            prompt=current_prompt,
            messages=history,
            tools=tools,
            tool_choice="required" if nudge_count > 0 else tool_choice,
            thinking=thinking,
        )

        # 发起 LLM 请求，捕获异常以防止整个循环崩溃
        try:
            await client.chat()
        except Exception as e:
            logger.error(
                f"[agent_loop:{name}] LLM 请求失败，第 {round_num} 轮，中止: {e}"
            )
            continue  # 继续下一轮，而不是中止整个循环

        # 首轮将 prompt 追加进历史（后续轮次 current_prompt 已置空，走 continuation 模式）
        if current_prompt:
            history.append(HumanMessage(content=current_prompt))
            current_prompt = ""

        # 无论 stop 还是 tool_calls，都先把本轮 AI 回复追加进历史，保证返回时历史完整
        ai_message = client.response_ai_message
        if ai_message is None:
            logger.error(f"[agent_loop:{name}] LLM 回复消息为空，中止")
            return False

        # 记录本轮 AI 回复的内容，便于调试
        history.append(ai_message)

        # 检查 LLM 的 finish_reason，决定下一步动作
        if client.finish_reason == "stop":
            # 未声明终止工具：stop 即正常结束（保持原有语义）
            if not terminal_tool_names:
                logger.debug(f"[agent_loop:{name}] LLM stop，第 {round_num} 轮")
                return True

            # 声明了终止工具却直接 stop：视为未完成，注入纠偏提示并重试
            nudge_count += 1
            if nudge_count > max_terminal_nudges:
                logger.error(
                    f"[agent_loop:{name}] LLM 连续 {max_terminal_nudges} 次未调用终止工具即停止，中止"
                )
                return False

            # 注入纠偏提示，提示 LLM 必须调用终止工具
            logger.warning(
                f"[agent_loop:{name}] LLM 未调用终止工具即 stop，"
                f"注入纠偏提示重试（第 {nudge_count}/{max_terminal_nudges} 次）"
            )

            # 将纠偏提示添加到历史记录中，供 LLM 在下一轮使用
            history.append(HumanMessage(content=_build_terminal_nudge(terminal_tools)))
            continue

        # 如果 finish_reason 不是 "stop" 且不是 "tool_calls"，说明出现了意外情况，记录错误并中止
        if client.finish_reason != "tool_calls" or not client.tool_calls:
            logger.error(
                f"[agent_loop:{name}] 意外的 finish_reason={client.finish_reason!r}，中止"
            )
            return False

        # 遍历 LLM 的工具调用列表，依次处理每个工具调用，根据工具名称找到对应的处理函数并执行，捕获异常以防止整个循环崩溃
        terminal_seen = False
        terminal_name: Optional[str] = None
        for tc in client.tool_calls:

            # 根据工具调用的名称找到对应的处理函数，如果找不到则记录警告并返回错误信息，否则执行处理函数并捕获异常
            handler = handlers.get(tc.function.name)
            succeeded = False

            # 检查当前工具调用是否有对应的处理函数，如果没有则记录警告并返回错误信息
            if handler is None:
                # 如果工具调用的名称在 handlers 中找不到对应的处理函数，记录警告并返回错误信息
                logger.warning(f"[agent_loop:{name}] 未知工具: {tc.function.name!r}")
                result = f"错误：未知工具 {tc.function.name!r}"

            else:

                # 执行工具调用，传入解析后的参数，如果执行失败则记录错误并返回错误信息
                try:
                    raw_result = handler(**json.loads(tc.function.arguments))
                    # 兼容 async handler：同步 handler 原样使用，异步 handler 在此 await
                    if inspect.isawaitable(raw_result):
                        result = await raw_result
                    else:
                        result = raw_result
                    succeeded = True
                except Exception as e:
                    logger.error(
                        f"[agent_loop:{name}] 工具 {tc.function.name!r} 执行失败: {e}\n"
                        f"  raw arguments: {tc.function.arguments!r}"
                    )
                    result = f"错误：工具执行失败 {e}"

            # 将工具调用的结果添加到历史记录中，以便在下一轮继续使用
            history.append(ToolMessage(content=result, tool_call_id=tc.id))

            # 只有真正执行成功的终止工具才结束循环；失败时错误已回写历史，进入下一轮让 LLM 重试。
            # 本轮所有工具调用处理完毕后统一退出，避免同一回复中终止工具排在其它工具之前时遗漏后续工具。
            if succeeded and tc.function.name in terminal_tool_names:
                terminal_seen = True
                terminal_name = tc.function.name

        # 终止工具已执行：本轮其余工具调用也已处理完毕，提前结束循环
        if terminal_seen:
            logger.debug(
                f"[agent_loop:{name}] 终止工具 {terminal_name!r} 已执行，结束循环"
            )
            return True

    # 如果循环结束仍未遇到 LLM stop，说明达到最大轮次限制，记录错误并中止
    logger.error(f"[agent_loop:{name}] 达到最大轮次限制 {max_rounds}，中止")
    return False
