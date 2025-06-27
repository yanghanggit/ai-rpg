"""
配置模块

包含项目的所有配置设置，包括：
- 服务器端口配置
- 聊天服务配置
- 游戏服务配置
"""

from .server_config import (
    chat_service_base_port,
    num_chat_service_instances,
    game_server_port,
    chat_service_path,
    chat_server_localhost_urls,
)

__all__ = [
    "chat_service_base_port",
    "num_chat_service_instances",
    "game_server_port",
    "chat_service_path",
    "chat_server_localhost_urls",
]
