"""
ChromaDB 向量数据库模块

该模块提供了ChromaDB向量数据库的客户端和相关功能。
"""

from .client import (
    chroma_client,
    reset_client,
    get_default_collection,
    get_custom_collection,
)
from .knowledge_retrieval import (
    add_documents,
    search_documents,
)

__all__ = [
    "chroma_client",
    "reset_client",
    "get_default_collection",
    "get_custom_collection",
    "add_documents",
    "search_documents",
]
