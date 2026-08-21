"""批量（batch）行为工具函数。

提供批量并发 chat 与批量并发 agent_loop 的封装。
"""

import asyncio
import time
from typing import Callable, Dict, List, Literal

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict

from ..models.messages import BaseMessage
from .agent_loop import agent_loop
from .client import DeepSeekClient, ToolDefinition


############################################################################################################
class AgentLoopConfig(BaseModel):
    """单次 agent_loop 的配置。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    prompt: str
    context: List[
        BaseMessage
    ]  # agent_loop 会原地修改该列表；需隔离时请传入各自独立的副本
    tools: List[ToolDefinition] = []
    handlers: Dict[str, Callable[..., str]] = {}
    max_rounds: int = 5
    tool_choice: Literal["auto", "none", "required"] = "auto"
    thinking: bool = False


############################################################################################################
async def batch_chat(clients: List[DeepSeekClient]) -> None:
    """批量并发发送聊天请求。

    创建一个共享 httpx.AsyncClient，所有 chat() 复用同一连接池，
    batch 结束后自动关闭。
    """
    if not clients:
        return

    start_time = time.time()
    async with httpx.AsyncClient() as shared_client:
        results = await asyncio.gather(
            *[c.chat(client=shared_client) for c in clients],
            return_exceptions=True,
        )
    elapsed = time.time() - start_time
    logger.debug(f"batch_chat: {len(clients)} clients, {elapsed:.2f}s")

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            name = clients[i].name if i < len(clients) else "unknown"
            logger.error(
                f"Request failed for '{name}': {type(result).__name__}: {result}"
            )

    failed = sum(1 for r in results if isinstance(r, BaseException))
    if failed:
        logger.warning(f"batch_chat: {failed}/{len(clients)} failed")
    else:
        logger.debug(f"batch_chat: all {len(clients)} requests succeeded")


############################################################################################################
async def batch_agent_loop(
    configs: List[AgentLoopConfig],
) -> List[bool]:
    """批量并发执行 agent_loop。

    每个元素是一个 AgentLoopConfig，参数含义与 agent_loop() 一致。
    agent_loop 会原地修改每个 config.context，调用结束后可通过 cfg.context 读取最终历史。
    注意：Pydantic 在构造 config 时会复制传入的 list，因此多个 config 共享同一基础列表是安全的，
    但原始列表不会被修改，最终历史只能通过 cfg.context 读取。
    返回与 configs 等长的 bool 列表，表示每个 agent_loop 是否成功。
    """
    if not configs:
        return []

    logger.info(f"batch_agent_loop: 启动 {len(configs)} 个 agent_loop")

    start_time = time.time()
    results = await asyncio.gather(
        *[
            agent_loop(
                name=cfg.name,
                prompt=cfg.prompt,
                context=cfg.context,
                tools=cfg.tools,
                handlers=cfg.handlers,
                max_rounds=cfg.max_rounds,
                tool_choice=cfg.tool_choice,
                thinking=cfg.thinking,
            )
            for cfg in configs
        ],
        return_exceptions=True,
    )
    elapsed = time.time() - start_time

    outcomes: List[bool] = []
    for i, result in enumerate(results):
        name = configs[i].name
        if isinstance(result, BaseException):
            logger.error(
                f"batch_agent_loop '{name}' 异常: {type(result).__name__}: {result}"
            )
            outcomes.append(False)
        else:
            logger.info(f"batch_agent_loop '{name}': {'成功' if result else '失败'}")
            outcomes.append(bool(result))

    succeeded = sum(1 for o in outcomes if o)
    logger.info(f"batch_agent_loop: {succeeded}/{len(configs)} 成功, {elapsed:.2f}s")
    return outcomes


############################################################################################################
