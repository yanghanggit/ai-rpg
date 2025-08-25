from pathlib import Path
from typing import Final, List

from pydantic import BaseModel


class ServerSettingsConfig(BaseModel):
    chat_service_base_port: int
    num_chat_service_instances: int
    game_server_port: int = 8000  # 默认值
    chat_service_endpoint: str = "/chat-service/v1/"  # 默认值
    # mcp_server_host: str = "127.0.0.1"  # MCP 服务器主机地址
    # mcp_server_port: int = 8765  # MCP 服务器端口
    # protocol_version: str = "2025-06-18"  # MCP 协议版本
    # mcp_timeout: int = 30  # 超时时间

    # @property
    # def mcp_server_url(self) -> str:
    #     """MCP 服务器完整URL地址"""
    #     return f"http://{self.mcp_server_host}:{self.mcp_server_port}"

    @property
    def chat_server_localhost_urls(self) -> List[str]:

        assert (
            self.num_chat_service_instances > 0
        ), "Number of chat service instances must be greater than 0"
        assert (
            self.chat_service_base_port > 0
        ), "Chat service base port must be greater than 0"

        """获取所有聊天服务器的 URL 列表"""
        ret: List[str] = []
        for i in range(self.num_chat_service_instances):
            ret.append(
                f"http://localhost:{self.chat_service_base_port + i}{self.chat_service_endpoint}"
            )
        return ret


# 配置文件路径
server_setting_path: Path = Path("server_settings.json")
assert (
    server_setting_path.exists()
), f"server_settings.json not found in {server_setting_path.parent}"
DEFAULT_SERVER_SETTINGS_CONFIG: Final[ServerSettingsConfig] = (
    ServerSettingsConfig.model_validate_json(
        server_setting_path.read_text(encoding="utf-8")
    )
)
assert (
    DEFAULT_SERVER_SETTINGS_CONFIG.chat_service_base_port > 0
), "chat_service_base_port must be greater than 0"
assert (
    DEFAULT_SERVER_SETTINGS_CONFIG.num_chat_service_instances > 0
), "num_chat_service_instances must be greater than 0"
assert (
    DEFAULT_SERVER_SETTINGS_CONFIG.game_server_port > 0
), "game_server_port must be greater than 0"


##################################################################################################################
