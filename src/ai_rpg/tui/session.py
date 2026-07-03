"""游戏会话状态数据类"""

from dataclasses import dataclass, field

from ..models import Blueprint, PlayerSession


@dataclass
class GameSession:
    """玩家登录后存续的会话状态。登出时销毁，重登时重建。"""

    player_session: PlayerSession
    blueprint: Blueprint
    last_sequence_id: int = field(default=0)

    @property
    def user_name(self) -> str:
        return self.player_session.name

    @property
    def game_name(self) -> str:
        return self.player_session.game
