"""通用 agentic 循环工具函数。"""

import inspect
import json
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Final,
    List,
    Literal,
    Optional,
    Union,
)

from loguru import logger

from ..llm.protocol import ChatClientProtocol
from ..llm.types import ToolDefinition
from ..models import ChatMessage, HumanMessage, ToolMessage
from .client import DeepSeekClient

#######################################################################################################################################
# loop 边界标记约定：起点 HumanMessage 携带 loop_id，本次 loop 追加的最后一条消息携带 loop_id_end。
# 两者均通过消息对象的额外属性（extra="allow"）承载，可随存档序列化往返保留。
LOOP_ID_ATTR: Final[str] = "loop_id"
LOOP_END_ATTR: Final[str] = "loop_id_end"


#######################################################################################################################################
@dataclass
class AgentLoopRound:
    """agent_loop 单轮的产物快照。

    - client: 本轮用于通讯的 client（按 ``ChatClientProtocol`` 标注），可读取
      finish_reason / tool_calls / usage / error 等「响应侧」信息。注意其
      messages 是共享 history 的引用，并非本轮快照；历史增量请看 ``appended``。
    - appended: 本轮向 history 追加的消息引用列表（按追加顺序）。
    """

    client: ChatClientProtocol
    appended: List[ChatMessage]


#######################################################################################################################################
@dataclass
class AgentLoopResult:
    """agent_loop 的完整结果。

    实现 ``__bool__``（成功即真），因此既有 ``ok = await agent_loop(...)`` 与
    ``if not ok:`` 写法无需改动。

    外部据此定位本次 loop 对 memory 的改动：
    - 改动范围：``messages[start_index:end_index]``（``messages`` 即 ``result.messages``）
    - 起点消息：``start_message``（本次 loop 追加的首条 HumanMessage；continuation
      模式未追加人类消息时为 None）
    - 中间过程：``rounds``（每轮的 client 与消息增量）

    ``messages`` 为本次 loop 实际操作的列表：``mutate_messages=True`` 时就是入参本身，
    ``False`` 时是入参的浅拷贝。
    """

    success: bool
    start_index: int
    end_index: int
    messages: List[ChatMessage]
    rounds: List[AgentLoopRound] = field(default_factory=list)
    start_message: Optional[HumanMessage] = None

    def __bool__(self) -> bool:
        return self.success


#######################################################################################################################################
class _LoopSpanTracker:
    """跟踪一次 agent_loop 对 history 的贡献：边界标记、改动范围与每轮增量。

    把原先散落在 agent_loop 内的闭包（记录轮次 / 打终点标记 / 收尾）收敛为一个对象，
    状态（history 引用、起点下标、loop_id、标记是否已打）由对象自己持有。
    """

    def __init__(self, history: List[ChatMessage], loop_id: Optional[str]) -> None:
        self._history = history
        self._loop_id = loop_id
        self.start_index = len(history)
        self.rounds: List[AgentLoopRound] = []
        self._start_marked = False

    ###################################################################################################################################
    def append_start_message(self, content: str, metadata: Dict[str, Any]) -> None:
        """追加本次 loop 的起点 HumanMessage；有 loop_id 时顺带打起点标记。"""
        extras = dict(metadata)
        if self._loop_id is not None:
            extras[LOOP_ID_ATTR] = self._loop_id
            self._start_marked = True
        self._history.append(HumanMessage(content=content, **extras))

    ###################################################################################################################################
    def record_round(self, client: ChatClientProtocol, round_start: int) -> None:
        """记录本轮：client 快照 + 本轮追加进 history 的消息引用。"""
        self.rounds.append(
            AgentLoopRound(client=client, appended=list(self._history[round_start:]))
        )

    ###################################################################################################################################
    def mark_end(self) -> None:
        """给本次 loop 追加的最后一条消息打终点标记（幂等）。

        仅在起点已打 loop_id 标记且确有追加消息时生效；正常返回、异常与取消路径都会调用。
        """
        if (
            self._loop_id is not None
            and self._start_marked
            and len(self._history) > self.start_index
        ):
            setattr(self._history[-1], LOOP_END_ATTR, self._loop_id)

    ###################################################################################################################################
    def build_result(self, success: bool) -> AgentLoopResult:
        """确保终点标记已打后，构建本次 loop 的结果。"""
        self.mark_end()
        candidate = (
            self._history[self.start_index]
            if self.start_index < len(self._history)
            else None
        )
        start_message = candidate if isinstance(candidate, HumanMessage) else None
        return AgentLoopResult(
            success=success,
            start_index=self.start_index,
            end_index=len(self._history),
            messages=self._history,
            rounds=self.rounds,
            start_message=start_message,
        )


#######################################################################################################################################
def _build_terminal_nudge(terminal_tools: List[ToolDefinition]) -> str:
    """构建「未调用终止工具即停止」时的纠偏提示。"""
    names = "、".join(t.function.name for t in terminal_tools)
    return f"你尚未调用要求的终止工具（{names}）就结束了回复。请勿以普通文本直接作答，必须通过工具调用提交最终结果；如仍需读取或写入数据，请先完成相应工具调用，最后再调用终止工具提交。"


#######################################################################################################################################
async def agent_loop(
    name: str,
    input_message: str,
    messages: List[ChatMessage],
    tools: List[ToolDefinition],
    handlers: Dict[str, Callable[..., Union[str, Awaitable[str]]]],
    mutate_messages: bool = True,
    max_rounds: int = 5,
    max_terminal_nudges: int = 2,
    tool_choice: Literal["auto", "none", "required"] = "auto",
    thinking: bool = False,
    terminal_tools: List[ToolDefinition] = [],
    input_metadata: Optional[Dict[str, Any]] = None,
    loop_id: Optional[str] = None,
) -> AgentLoopResult:
    """通用 agentic 循环：驱动 LLM 与工具交互，直到 LLM 主动 stop、调用 terminal_tools 中任一或达到最大轮次。

    当声明了 terminal_tools 时，`finish_reason == "stop"` 不再等同于正常结束：
    若尚未成功调用任一终止工具，则视为未完成，注入纠偏提示后强制重试（最多
    `max_terminal_nudges` 次），避免 LLM 把结果当作普通文本输出而丢失结算。

    返回值 ``AgentLoopResult`` 携带本次 loop 对 memory 的改动范围（start_index /
    end_index）、起点消息（start_message）与每轮过程（rounds）。

    标记与查询：
    - ``input_metadata`` 作为额外属性外挂在起点 HumanMessage 上（纯附加信息）；
    - ``loop_id`` 非空时，起点 HumanMessage 会带上 ``LOOP_ID_ATTR == loop_id``，
      本次 loop 追加的最后一条消息会带上 ``LOOP_END_ATTR == loop_id``（异常/取消
      路径也会补打终点标记），使外部可用 ``models.messages.find_marked_span``
      （``start_attr=LOOP_ID_ATTR``，``end_attr=LOOP_END_ATTR``）在存档记忆中反查边界。

    ``mutate_messages``（默认 True）控制是否原地修改入参 ``messages``：为 False 时
    在入参的浅拷贝上工作，调用方列表与持久记忆不被改动（注意这不等同于上下文隔离，
    入参带什么历史就仍会发给 LLM）；两种模式下改动范围都是
    ``result.messages[start_index:end_index]``。
    """
    # 默认原地追加（方案 C）；mutate_messages=False 时在浅拷贝上工作。
    # 浅拷贝（仅复制列表结构、共享消息对象）已足够：循环只做 append，唯一的
    # setattr(LOOP_END_ATTR) 目标是循环内新建的消息。
    history: List[ChatMessage] = messages if mutate_messages else list(messages)
    current_prompt = input_message
    terminal_tool_names = {t.function.name for t in terminal_tools}
    nudge_count = 0

    # 本次 loop 对 history 的贡献（边界标记 / 改动范围 / 每轮增量）由 tracker 统一记录。
    tracker = _LoopSpanTracker(history, loop_id)

    try:
        # 进入 agent 循环，每轮与 LLM 交互，处理工具调用，直到 LLM 主动 stop 或达到最大轮次
        for round_num in range(1, max_rounds + 1):
            logger.debug(f"[agent_loop:{name}] 第 {round_num}/{max_rounds} 轮")

            round_start = len(history)

            # 初始化 DeepSeekClient，用于与 LLM 进行交互，传入当前轮次的输入消息、消息历史、工具定义和工具选择策略。
            # 纠偏重试轮强制 tool_choice="required"，逼迫 LLM 通过工具调用而非普通文本作答。
            client = DeepSeekClient(
                label=name,
                input_message=current_prompt,
                messages=history,
                tools=tools,
                tool_choice="required" if nudge_count > 0 else tool_choice,
                thinking=thinking,
            )

            # 发起 LLM 请求，捕获异常以防止整个循环崩溃
            try:

                # 发起 LLM 请求，等待响应
                await client.chat()

            except Exception as e:

                logger.error(
                    f"[agent_loop:{name}] LLM 请求失败，第 {round_num} 轮，中止: {e}"
                )
                tracker.record_round(client, round_start)
                continue  # 继续下一轮，而不是中止整个循环

            # 首轮将输入消息追加进历史（后续轮次 current_prompt 已置空，走 continuation 模式）。
            # input_metadata 作为额外属性外挂；loop_id 额外写成 LOOP_ID_ATTR 供外部定位 loop 起点。
            if current_prompt:
                tracker.append_start_message(current_prompt, input_metadata or {})
                current_prompt = ""

            # 无论 stop 还是 tool_calls，都先把本轮 AI 回复追加进历史，保证返回时历史完整
            ai_message = client.response_ai_message
            if ai_message is None:
                logger.error(f"[agent_loop:{name}] LLM 回复消息为空，中止")
                tracker.record_round(client, round_start)
                return tracker.build_result(False)

            # 记录本轮 AI 回复的内容，便于调试
            history.append(ai_message)

            # 检查 LLM 的 finish_reason，决定下一步动作
            if client.finish_reason == "stop":

                # 未声明终止工具：stop 即正常结束（保持原有语义）
                if not terminal_tool_names:
                    logger.debug(f"[agent_loop:{name}] LLM stop，第 {round_num} 轮")
                    tracker.record_round(client, round_start)
                    return tracker.build_result(True)

                # 声明了终止工具却直接 stop：视为未完成，注入纠偏提示并重试
                nudge_count += 1
                if nudge_count > max_terminal_nudges:
                    logger.error(
                        f"[agent_loop:{name}] LLM 连续 {max_terminal_nudges} 次未调用终止工具即停止，中止"
                    )
                    tracker.record_round(client, round_start)
                    return tracker.build_result(False)

                # 注入纠偏提示，提示 LLM 必须调用终止工具
                logger.warning(
                    f"[agent_loop:{name}] LLM 未调用终止工具即 stop，注入纠偏提示重试（第 {nudge_count}/{max_terminal_nudges} 次）"
                )

                # 将纠偏提示添加到历史记录中，供 LLM 在下一轮使用
                history.append(
                    HumanMessage(content=_build_terminal_nudge(terminal_tools))
                )
                tracker.record_round(client, round_start)
                continue

            # 如果 finish_reason 不是 "stop" 且不是 "tool_calls"，说明出现了意外情况，记录错误并中止
            if client.finish_reason != "tool_calls" or not client.tool_calls:
                logger.error(
                    f"[agent_loop:{name}] 意外的 finish_reason={client.finish_reason!r}，中止"
                )
                tracker.record_round(client, round_start)
                return tracker.build_result(False)

            # 遍历 LLM 的工具调用列表，依次处理每个工具调用，根据工具名称找到对应的处理函数并执行，捕获异常以防止整个循环崩溃
            terminal_seen = False
            terminal_name: Optional[str] = None

            # 遍历本轮 LLM 的工具调用，依次处理每个工具调用
            for tc in client.tool_calls:

                # 根据工具调用的名称找到对应的处理函数，如果找不到则记录警告并返回错误信息，否则执行处理函数并捕获异常
                handler = handlers.get(tc.function.name)
                succeeded = False

                # 检查当前工具调用是否有对应的处理函数，如果没有则记录警告并返回错误信息
                if handler is None:
                    # 如果工具调用的名称在 handlers 中找不到对应的处理函数，记录警告并返回错误信息
                    logger.warning(
                        f"[agent_loop:{name}] 未知工具: {tc.function.name!r}"
                    )
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

                        # 工具调用成功，标记为 succeeded，result 已包含返回值
                        succeeded = True

                    except Exception as e:

                        logger.error(
                            f"[agent_loop:{name}] 工具 {tc.function.name!r} 执行失败: {e}\n  raw arguments: {tc.function.arguments!r}"
                        )
                        result = f"错误：工具执行失败 {e}"

                # 将工具调用的结果添加到历史记录中，以便在下一轮继续使用
                history.append(ToolMessage(content=result, tool_call_id=tc.id))

                # 只有真正执行成功的终止工具才结束循环；失败时错误已回写历史，进入下一轮让 LLM 重试。
                # 本轮所有工具调用处理完毕后统一退出，避免同一回复中终止工具排在其它工具之前时遗漏后续工具。
                if succeeded and tc.function.name in terminal_tool_names:
                    terminal_seen = True
                    terminal_name = tc.function.name

            tracker.record_round(client, round_start)

            # 终止工具已执行：本轮其余工具调用也已处理完毕，提前结束循环
            if terminal_seen:
                logger.debug(
                    f"[agent_loop:{name}] 终止工具 {terminal_name!r} 已执行，结束循环"
                )
                return tracker.build_result(True)

        # 如果循环结束仍未遇到 LLM stop，说明达到最大轮次限制，记录错误并中止
        logger.error(f"[agent_loop:{name}] 达到最大轮次限制 {max_rounds}，中止")
        return tracker.build_result(False)

    except BaseException:
        # 异常 / 取消（如 asyncio.CancelledError）穿透前补打终点标记，避免留下悬空起点。
        tracker.mark_end()
        raise
