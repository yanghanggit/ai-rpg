"""
配置模块

包含项目的所有配置设置，包括：
- 服务器端口配置
- 聊天服务配置
- 游戏服务配置
- 数据库配置（Redis、MongoDB、PostgreSQL）
- JWT配置
- 游戏配置（日志、游戏名称等）

注意：MCP配置已移至 multi_agents_game.mcp.config 模块
"""

from ..pgsql import (
    # DEFAULT_JWT_CONFIG,
    DEFAULT_POSTGRES_CONFIG,
    # DEFAULT_RAG_CONFIG,
    # DEFAULT_REDIS_CONFIG,
    # JWTConfig,
    PostgresConfig,
    # RAGConfig,
    # RedisConfig,
)
from ..mongodb import DEFAULT_MONGODB_CONFIG, MongoDBConfig
from ..game.game_config import (
    GLOBAL_GAME_NAME,
    LOGS_DIR,
    setup_logger,
)
from .server_settings_config import (
    DEFAULT_SERVER_SETTINGS_CONFIG,
)

__all__ = [
    # 服务器配置
    "DEFAULT_SERVER_SETTINGS_CONFIG",
    # 数据库配置类
    # "RedisConfig",
    "MongoDBConfig",
    "PostgresConfig",
    # "JWTConfig",
    # "RAGConfig",
    # 数据库配置实例
    # "DEFAULT_REDIS_CONFIG",
    "DEFAULT_MONGODB_CONFIG",
    "DEFAULT_POSTGRES_CONFIG",
    # "DEFAULT_JWT_CONFIG",
    # "DEFAULT_RAG_CONFIG",
    # 游戏配置
    "LOGS_DIR",
    "GLOBAL_GAME_NAME",
    "setup_logger",
]
