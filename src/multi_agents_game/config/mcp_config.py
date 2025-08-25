from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger


##################################################################################################################
class McpConfig(BaseModel):
    mcp_server_host: str = Field(..., description="MCP 服务器主机地址")
    mcp_server_port: int = Field(..., description="MCP 服务器端口")
    protocol_version: str = Field(..., description="MCP 协议版本")
    mcp_timeout: int = Field(..., description="MCP 超时时间")

    @property
    def mcp_server_url(self) -> str:
        """MCP 服务器完整URL地址"""
        return f"http://{self.mcp_server_host}:{self.mcp_server_port}"


##################################################################################################################
def load_mcp_config(config_path: Path) -> Optional[McpConfig]:
    try:
        assert config_path.exists(), f"{config_path} not found"
        mcp_config = McpConfig.model_validate_json(
            config_path.read_text(encoding="utf-8")
        )

        logger.info(f"MCP Config loaded from {config_path}: {mcp_config}")

        return mcp_config
    except Exception as e:
        logger.error(f"Error loading MCP config: {e}")
        return None


##################################################################################################################
