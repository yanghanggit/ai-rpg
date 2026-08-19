"""
RAG（检索增强生成）模块

桥接 SentenceTransformer 嵌入模型与 pgvector 存储层，
提供文档加载与语义检索的高层 API。
"""

from .knowledge_retrieval import add_documents, search_documents, delete_collection

__all__ = [
    "add_documents",
    "search_documents",
    "delete_collection",
]
