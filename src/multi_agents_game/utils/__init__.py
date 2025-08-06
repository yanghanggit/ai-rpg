"""
Multi-Agents Game Framework 工具模块

这个包包含了游戏框架中使用的各种工具和实用函数。

主要模块：
- json_format: JSON格式化和处理工具
- model_loader: SentenceTransformer模型加载工具
"""

# JSON格式化工具
from .json_format import (
    clean_json_string,
    combine_json_fragments,
    contains_duplicate_segments,
    contains_json_code_block,
    strip_json_code_block,
)

# 模型加载工具
from .model_loader import ModelLoader

# 公开的API
__all__ = [
    # JSON格式化工具
    "clean_json_string",
    "combine_json_fragments",
    "contains_duplicate_segments",
    "contains_json_code_block",
    "strip_json_code_block",
    # 模型加载工具
    "ModelLoader",
]
