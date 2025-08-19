"""
MCP 客户端

用于与 MCP 工具服务器通信的客户端类。
提供标准化的工具发现、调用和错误处理功能。
"""

from typing import Any, Dict, List, Optional

import aiohttp
from loguru import logger

from pydantic import BaseModel


class McpToolInfo(BaseModel):
    """MCP 工具信息"""

    name: str
    description: str
    input_schema: Dict[str, Any]


class McpToolResult(BaseModel):
    """MCP 工具执行结果"""

    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float


class McpClient:
    """MCP 客户端"""

    def __init__(self, server_url: str):
        # if server_url is None:
        #     server_url = DEFAULT_SERVER_SETTINGS_CONFIG.mcp_server_url
        self.server_url = server_url.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None
        self._tools_cache: Optional[List[McpToolInfo]] = None

    async def __aenter__(self) -> "McpClient":
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()

    async def _ensure_session(self) -> None:
        """确保会话存在"""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def check_health(self) -> bool:
        """检查服务器健康状态"""
        try:
            await self._ensure_session()
            if self.session is None:
                return False
            async with self.session.get(f"{self.server_url}/health") as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False

    async def get_available_tools(
        self, force_refresh: bool = False
    ) -> List[McpToolInfo]:
        """获取可用工具列表"""
        if not force_refresh and self._tools_cache:
            return self._tools_cache

        try:
            await self._ensure_session()
            if self.session is None:
                return []
            async with self.session.get(f"{self.server_url}/tools") as response:
                if response.status != 200:
                    raise Exception(f"获取工具列表失败: HTTP {response.status}")

                tools_data = await response.json()
                tools = [McpToolInfo(**tool) for tool in tools_data]
                self._tools_cache = tools

                logger.info(f"获取到 {len(tools)} 个可用工具")
                return tools

        except Exception as e:
            logger.error(f"获取工具列表失败: {e}")
            return []

    async def get_tool_info(self, tool_name: str) -> Optional[McpToolInfo]:
        """获取指定工具信息"""
        try:
            await self._ensure_session()
            if self.session is None:
                return None
            async with self.session.get(
                f"{self.server_url}/tools/{tool_name}"
            ) as response:
                if response.status == 404:
                    return None
                elif response.status != 200:
                    raise Exception(f"获取工具信息失败: HTTP {response.status}")

                tool_data = await response.json()
                return McpToolInfo(**tool_data)

        except Exception as e:
            logger.error(f"获取工具信息失败: {tool_name} | {e}")
            return None

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> McpToolResult:
        """调用工具"""
        try:
            await self._ensure_session()
            if self.session is None:
                raise Exception("Session not initialized")

            request_data = {"arguments": arguments}

            async with self.session.post(
                f"{self.server_url}/tools/{tool_name}/call", json=request_data
            ) as response:
                if response.status != 200:
                    raise Exception(f"工具调用失败: HTTP {response.status}")

                result_data = await response.json()
                result = McpToolResult(**result_data)

                if result.success:
                    logger.info(f"工具调用成功: {tool_name} -> {result.result}")
                else:
                    logger.error(f"工具调用失败: {tool_name} -> {result.error}")

                return result

        except Exception as e:
            logger.error(f"工具调用异常: {tool_name} | {e}")
            return McpToolResult(
                success=False, result=None, error=str(e), execution_time=0.0
            )

    async def call_tool_simple(self, tool_name: str, **kwargs: Any) -> Any:
        """简化的工具调用方法，直接返回结果"""
        result = await self.call_tool(tool_name, kwargs)
        if result.success:
            return result.result
        else:
            raise Exception(result.error or "工具调用失败")

    def format_tools_for_prompt(self, tools: Optional[List[McpToolInfo]] = None) -> str:
        """格式化工具信息用于提示词"""
        if tools is None:
            # 同步获取工具列表（注意：这里需要在异步上下文中调用）
            return "获取工具列表失败"

        if not tools:
            return "当前没有可用工具"

        tool_descriptions = []
        for tool in tools:
            params_desc = ""

            if tool.input_schema and "properties" in tool.input_schema:
                param_list = []
                properties = tool.input_schema["properties"]
                required = tool.input_schema.get("required", [])

                for param_name, param_info in properties.items():
                    param_desc = param_info.get("description", "无描述")
                    is_required = " (必需)" if param_name in required else " (可选)"
                    param_list.append(f"{param_name}: {param_desc}{is_required}")

                params_desc = f" 参数: {', '.join(param_list)}" if param_list else ""

            tool_desc = f"- {tool.name}: {tool.description}{params_desc}"
            tool_descriptions.append(tool_desc)

        return "\n".join(tool_descriptions)
