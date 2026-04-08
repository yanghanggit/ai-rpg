"""游戏会话状态数据类"""

from dataclasses import dataclass, field

from ..models import Blueprint


@dataclass
class GameSession:
    """玩家登录后存续的会话状态。登出时销毁，重登时重建。"""

    user_name: str
    game_name: str
    blueprint: Blueprint
    last_sequence_id: int = field(default=0)
