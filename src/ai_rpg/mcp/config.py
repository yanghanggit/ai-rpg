"""
MCP配置管理模块

提供MCP服务器配置的加载和管理功能
"""

from pathlib import Path
from typing import Final, List
from pydantic import BaseModel
from loguru import logger


class McpConfig(BaseModel):
    """MCP服务器配置模型"""

    mcp_server_host: str = "127.0.0.1"
    mcp_server_port: int = 8765
    protocol_version: str = "2025-06-18"
    mcp_timeout: int = 30

    # 服务器配置
    server_name: str = "Production MCP Server"
    server_version: str = "1.0.0"
    server_description: str = "生产级 MCP 服务器，支持工具调用、资源访问和提示模板"
    transport: str = "streamable-http"
    allowed_origins: List[str] = ["http://localhost"]

    @property
    def mcp_server_url(self) -> str:
        """MCP 服务器完整URL地址"""
        return f"http://{self.mcp_server_host}:{self.mcp_server_port}"

    @property
    def complete_allowed_origins(self) -> List[str]:
        """获取完整的允许来源列表，包括动态生成的主机地址"""
        origins = self.allowed_origins.copy()
        host_origin = f"http://{self.mcp_server_host}"
        if host_origin not in origins:
            origins.append(host_origin)
        return origins


###########################################################################################
# 加载默认MCP配置
mcp_config: Final[McpConfig] = McpConfig()

try:
    MCP_CONFIG_PATH: Path = Path("mcp_config.json")
    if not MCP_CONFIG_PATH.exists():
        logger.error(f"MCP 配置文件不存在: {MCP_CONFIG_PATH}")
        MCP_CONFIG_PATH.write_text(
            mcp_config.model_dump_json(indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"已创建默认 MCP 配置文件: {MCP_CONFIG_PATH}")

except Exception as e:
    logger.error(f"加载 MCP 配置文件失败: {e}")
###########################################################################################
