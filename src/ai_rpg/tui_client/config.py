"""TUI 客户端配置"""

from dataclasses import dataclass


@dataclass
class ServerConfig:
    """游戏服务器连接配置（可在启动时动态设置）。"""

    host: str
    port: int

    @property
    def base_url(self) -> str:
        assert self.host and self.port, "服务器 host 和 port 必须设置"
        return f"http://{self.host}:{self.port}"


server_config = ServerConfig(host="localhost", port=8000)
