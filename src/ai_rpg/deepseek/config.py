"""DeepSeek 模块公共配置常量"""

from pathlib import Path
from typing import Final

# DeepSeek 模型名称
MODEL_FLASH: Final[str] = (
    "deepseek-flash"  # DeepSeek-V4.1-Flash，支持视觉（旧名 deepseek-v4-flash 已下线）
)
MODEL_PRO: Final[str] = (
    "deepseek-v4-pro"  # V4 Pro（已下线；2026-09-14 起请求路由到 V4.1 Flash，按 Flash 计费）
)

# chat dump 全局开关（默认关闭）；run_agent_game.py 等调试入口会在运行时打开
CHAT_DUMP_ENABLED: bool = False

# chat dump 存储目录（项目根目录下）
CHAT_DUMP_DIR: Path = Path(".chat_dumps")
CHAT_DUMP_DIR.mkdir(parents=True, exist_ok=True)
