"""TUI 客户端配置"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ServerConfig:
    """游戏服务器连接配置（可在启动时动态设置）。

    port 不设默认值：必须由外部显式设置（见 scripts/run_tui.py），
    避免任何端口（例如 8000）成为潜规则。
    """

    host: str
    port: Optional[int] = None

    @property
    def base_url(self) -> str:
        if self.host is None or self.port is None:
            raise RuntimeError(
                "服务器 host 和 port 必须由外部设置（见 scripts/run_tui.py）"
            )
        return f"http://{self.host}:{self.port}"


server_config = ServerConfig(host="localhost")
