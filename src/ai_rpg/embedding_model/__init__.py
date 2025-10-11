"""
嵌入模型模块

提供 SentenceTransformer 模型的加载和管理功能。
"""

from .model_loader import (
    ModelLoader,
    is_model_cached,
    load_basic_model,
    load_multilingual_model,
    load_sentence_transformer,
)
from .sentence_transformer import (
    # clear_embedding_model,
    get_embedding_model,
)

__all__ = [
    # model_loader
    "ModelLoader",
    "is_model_cached",
    "load_basic_model",
    "load_multilingual_model",
    "load_sentence_transformer",
    # sentence_transformer_embedding_model
    # "clear_embedding_model",
    "get_embedding_model",
]
