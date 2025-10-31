"""
嵌入模型模块

提供 SentenceTransformer 模型的加载和管理功能。
"""

from .config import (
    SENTENCE_TRANSFORMERS_CACHE,
    cache_path,
    is_model_cached,
)
from .sentence_transformer import (
    multilingual_model,
)

__all__ = [
    "SENTENCE_TRANSFORMERS_CACHE",
    "cache_path",
    "is_model_cached",
    "multilingual_model",
]
