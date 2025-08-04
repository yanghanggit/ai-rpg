"""
配置模块

包含项目的所有配置设置，包括：
- 服务器端口配置
- 聊天服务配置
- 游戏服务配置
"""

from .server_settings_config import (
    DEFAULT_SERVER_SETTINGS_CONFIG,
)

__all__ = [
    "DEFAULT_SERVER_SETTINGS_CONFIG",
]
