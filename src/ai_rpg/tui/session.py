"""客户端会话状态数据类"""

from dataclasses import dataclass, field
from typing import Optional

from ..models import Blueprint, PlayerSession


@dataclass
class ClientSession:
    """玩家登录后存续的客户端会话状态。登出时销毁，重登时重建。"""

    player_session: PlayerSession
    blueprint: Blueprint
    last_sequence_id: int = field(default=0)
    notify_last_sequence_id: int = field(default=0)
    """通知监听（_watch_notifications）探测到的服务端最高 sequence_id（高水位线），
    仅用于计算未读数量，不代表消息已被读取/展示。"""
    _storage_entity_name: Optional[str] = field(default=None, repr=False)

    @property
    def user_name(self) -> str:
        return self.player_session.name

    @property
    def game_name(self) -> str:
        return self.player_session.game

    @property
    def actor_name(self) -> str:
        return self.player_session.actor
