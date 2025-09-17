"""
MCP工具执行模块

提供MCP客户端初始化和工具执行功能
"""

import asyncio
import time
from typing import Any, Dict, Tuple
from loguru import logger

from .client import McpClient


async def initialize_mcp_client(
    mcp_server_url: str, mcp_protocol_version: str, mcp_timeout: int
) -> McpClient:
    """
    初始化 MCP 客户端

    Args:
        mcp_server_url: MCP 服务器地址（Streamable HTTP 模式）
        mcp_protocol_version: MCP 协议版本
        mcp_timeout: 超时时间

    Returns:
        McpClient: 初始化后的 MCP 客户端
    """
    # 使用 Streamable HTTP 模式（标准 2025-06-18 规范）
    client = McpClient(
        base_url=mcp_server_url,
        protocol_version=mcp_protocol_version,
        timeout=mcp_timeout,
    )

    # 连接到服务器
    await client.connect()

    # 检查服务器健康状态
    if not await client.check_health():
        await client.disconnect()
        raise ConnectionError(f"无法连接到 MCP 服务器: {mcp_server_url}")

    logger.info(f"MCP 客户端初始化成功: {mcp_server_url}")
    return client


async def execute_mcp_tool(
    tool_name: str,
    tool_args: Dict[str, Any],
    mcp_client: McpClient,
    timeout: float = 30.0,
    max_retries: int = 2,
) -> Tuple[bool, str, float]:
    """
    通过 MCP 客户端执行工具（增强版）

    Args:
        tool_name: 工具名称
        tool_args: 工具参数
        mcp_client: MCP 客户端
        timeout: 超时时间（秒）
        max_retries: 最大重试次数

    Returns:
        Tuple[bool, str, float]: (成功标志, 结果或错误信息, 执行时间)
    """
    start_time = time.time()

    for attempt in range(max_retries + 1):
        try:
            # 使用asyncio.wait_for添加超时控制
            result = await asyncio.wait_for(
                mcp_client.call_tool(tool_name, tool_args), timeout=timeout
            )

            execution_time = time.time() - start_time

            if result.success:
                logger.info(
                    f"🔧 MCP工具执行成功: {tool_name} | 参数: {tool_args} | "
                    f"耗时: {execution_time:.2f}s | 尝试: {attempt + 1}/{max_retries + 1}"
                )
                return True, str(result.result), execution_time
            else:
                error_msg = f"工具执行失败: {tool_name} | 错误: {result.error}"
                logger.error(f"❌ {error_msg} | 尝试: {attempt + 1}/{max_retries + 1}")

                # 如果是最后一次尝试，返回错误
                if attempt == max_retries:
                    return False, error_msg, time.time() - start_time

        except asyncio.TimeoutError:
            error_msg = f"工具执行超时: {tool_name} | 超时时间: {timeout}s"
            logger.error(f"⏰ {error_msg} | 尝试: {attempt + 1}/{max_retries + 1}")

            if attempt == max_retries:
                return False, error_msg, time.time() - start_time

        except Exception as e:
            error_msg = f"工具执行异常: {tool_name} | 错误: {str(e)}"
            logger.error(f"💥 {error_msg} | 尝试: {attempt + 1}/{max_retries + 1}")

            if attempt == max_retries:
                return False, error_msg, time.time() - start_time

        # 重试前等待
        if attempt < max_retries:
            wait_time = min(2**attempt, 5)  # 指数退避，最大5秒
            logger.info(f"🔄 等待 {wait_time}s 后重试...")
            await asyncio.sleep(wait_time)

    # 理论上不会到达这里
    return False, "未知错误", time.time() - start_time
