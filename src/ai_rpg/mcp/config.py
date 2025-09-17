"""
MCP配置管理模块

提供MCP服务器配置的加载和管理功能
"""

from pathlib import Path
from typing import List
from pydantic import BaseModel, Field
from loguru import logger


class McpConfig(BaseModel):
    """MCP服务器配置模型"""

    mcp_server_host: str = Field(..., description="MCP 服务器主机地址")
    mcp_server_port: int = Field(..., description="MCP 服务器端口")
    protocol_version: str = Field(..., description="MCP 协议版本")
    mcp_timeout: int = Field(..., description="MCP 超时时间")

    # 服务器配置
    server_name: str = Field(..., description="MCP 服务器名称")
    server_version: str = Field(..., description="MCP 服务器版本")
    server_description: str = Field(..., description="MCP 服务器描述")
    transport: str = Field(..., description="MCP 传输协议")
    allowed_origins: List[str] = Field(..., description="允许的来源列表")

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


def load_mcp_config(config_path: Path) -> McpConfig:
    """
    加载MCP配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        McpConfig: MCP配置对象

    Raises:
        RuntimeError: 配置加载失败时抛出
    """
    try:
        assert config_path.exists(), f"{config_path} not found"
        mcp_config = McpConfig.model_validate_json(
            config_path.read_text(encoding="utf-8")
        )

        logger.info(f"MCP Config loaded from {config_path}: {mcp_config}")

        return mcp_config
    except Exception as e:
        logger.error(f"Error loading MCP config: {e}")
        raise RuntimeError("Failed to load MCP config")
