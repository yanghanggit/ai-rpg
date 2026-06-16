"""DeepSeek 模块公共配置常量"""

from pathlib import Path
from typing import Final

# DeepSeek 模型名称
MODEL_FLASH: Final[str] = "deepseek-v4-flash"  # 轻量快速模型
MODEL_PRO: Final[str] = "deepseek-v4-pro"  # 高能力模型

# chat dump 全局开关（默认开启）；设为 False 可关闭所有 chat() 的 md dump
CHAT_DUMP_ENABLED: bool = True

# chat dump 存储目录（项目根目录下）
CHAT_DUMP_DIR: Path = Path(".chat_dumps")
CHAT_DUMP_DIR.mkdir(parents=True, exist_ok=True)
