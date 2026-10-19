"""DeepSeek 绑定入口：把 `ai_rpg.llm.agent_loop` 绑定到 `DeepSeekClient`。

分工
----
- 编排逻辑在 `ai_rpg.llm.agent_loop`（provider 无关，通过 `create_client` 注入）；
- 「用哪个 provider」只在这里决定一次（组合点），业务系统不重复传工厂。

签名为什么和 `ai_rpg.llm.agent_loop.agent_loop` 逐字重复
--------------------------------------------------------
`functools.partial(_agent_loop, create_client=DeepSeekClient)` 更短，但有两个问题：
1. 测试无法再 `patch("ai_rpg.deepseek.agent_loop.DeepSeekClient")`——partial 在 import
   时就捕获了类对象，替换失效会真的发 HTTP；本模块改为在**调用时**查模块全局；
2. `partial` 的类型是 `partial[Coroutine[...]]`，调用方参数不再被 mypy 检查。

显式重复参数表可同时解决两点；参数漂移由
`tests/unit/test_llm_protocol.py::test_deepseek_agent_loop_binding_mirrors_llm_signature` 守护。
"""

from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from ..llm.agent_loop import (
    LOOP_END_ATTR,
    LOOP_ID_ATTR,
    AgentLoopResult,
    AgentLoopRound,
)
from ..llm.agent_loop import (
    agent_loop as _agent_loop,
)
from ..llm.types import ToolChoice, ToolDefinition
from ..models import ChatMessage
from .client import DeepSeekClient

__all__ = [
    "AgentLoopResult",
    "AgentLoopRound",
    "LOOP_END_ATTR",
    "LOOP_ID_ATTR",
    "agent_loop",
]


############################################################################################################
async def agent_loop(
    name: str,
    input_message: str,
    messages: List[ChatMessage],
    tools: List[ToolDefinition],
    handlers: Dict[str, Callable[..., Union[str, Awaitable[str]]]],
    mutate_messages: bool = True,
    max_rounds: int = 5,
    max_terminal_nudges: int = 2,
    tool_choice: ToolChoice = "auto",
    thinking: bool = False,
    terminal_tools: List[ToolDefinition] = [],
    input_metadata: Optional[Dict[str, Any]] = None,
    loop_id: Optional[str] = None,
) -> AgentLoopResult:
    """`ai_rpg.llm.agent_loop.agent_loop` 的 DeepSeek 绑定版本（参数语义完全相同）。"""
    return await _agent_loop(
        name=name,
        input_message=input_message,
        messages=messages,
        tools=tools,
        handlers=handlers,
        mutate_messages=mutate_messages,
        max_rounds=max_rounds,
        max_terminal_nudges=max_terminal_nudges,
        tool_choice=tool_choice,
        thinking=thinking,
        terminal_tools=terminal_tools,
        input_metadata=input_metadata,
        loop_id=loop_id,
        create_client=DeepSeekClient,
    )
