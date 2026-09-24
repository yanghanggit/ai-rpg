"""游戏服务器连接配置（API Agent）"""

from dataclasses import dataclass
from typing import Dict, Optional, Union


@dataclass
class ServerConfig:
    """游戏服务器连接配置（可在启动时动态设置）。

    port 不设默认值：必须由外部显式设置（见 ai_rpg/cli/agent_api.py），
    避免任何端口（例如 8000）成为潜规则。

    scheme / verify / auth_token 为将来的 HTTPS 与 JWT 预留：
    - scheme: ``"http"``（默认）或 ``"https"``；
    - verify: ``True``/``False``，或 CA bundle 路径字符串（httpx 语义）；
    - auth_token: 非空时以 ``Authorization: Bearer <token>`` 注入所有请求。
    """

    host: str
    port: Optional[int] = None
    scheme: str = "http"
    verify: Union[bool, str] = True
    auth_token: Optional[str] = None

    @property
    def base_url(self) -> str:
        if self.host is None or self.port is None:
            raise RuntimeError(
                "服务器 host 和 port 必须由外部设置（见 ai_rpg/cli/agent_api.py）"
            )
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def headers(self) -> Dict[str, str]:
        """全局请求头：当前仅承载 JWT 鉴权（未配置 token 时为空）。"""
        if self.auth_token:
            return {"Authorization": f"Bearer {self.auth_token}"}
        return {}


server_config = ServerConfig(host="localhost")
