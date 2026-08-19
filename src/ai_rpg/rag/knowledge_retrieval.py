"""
RAG 知识检索模块（桥接 SentenceTransformer 与 pgvector）

此模块提供 RAG（检索增强生成）系统的文档管理和语义搜索功能：
1. 文档加载 - 将文档向量化并存储到 vector_documents 表
2. 语义搜索 - 基于向量相似度检索最相关的文档

核心功能：
- add_documents: 加载文档到向量数据库（纯工具函数，不含业务逻辑）
- search_documents: 执行语义搜索，返回最相关的文档和相似度分数
- delete_collection: 清空指定 collection 下的全部文档（开发/测试环境清理用）
"""

import traceback
from typing import Any, Dict, List, Tuple, cast
from loguru import logger
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sentence_transformers import SentenceTransformer
from ..pgsql.client import SessionLocal
from ..pgsql import save_vector_document, search_similar_documents


############################################################################################################
def add_documents(
    collection: str,
    embedding_model: SentenceTransformer,
    documents: List[str],
    metadatas: List[Dict[str, Any]],
) -> bool:
    """
    加载文档到向量数据库（纯工具函数）

    功能：
    1. 将文档向量化并存储到 vector_documents 表
    2. 不包含业务逻辑，由调用方准备所有数据

    Args:
        collection: 集合名称（用于隔离不同知识库，如游戏名）
        embedding_model: SentenceTransformer 嵌入模型实例
        documents: 文档列表
        metadatas: 元数据列表，与 documents 一一对应

    Returns:
        bool: 加载是否成功
    """
    try:
        if not documents:
            logger.warning("⚠️  [LOAD] 文档数据为空，跳过加载")
            return True

        if len(documents) != len(metadatas):
            logger.error(
                f"❌ [LOAD] 数据长度不一致: documents={len(documents)}, metadatas={len(metadatas)}"
            )
            return False

        logger.info(f"🚀 [LOAD] 开始加载 {len(documents)} 个文档...")
        logger.info("🔄 [LOAD] 计算文档向量嵌入...")
        embeddings = embedding_model.encode(documents).tolist()

        logger.info("💾 [LOAD] 存储向量到数据库...")
        for document, metadata, embedding in zip(documents, metadatas, embeddings):
            save_vector_document(
                content=document,
                embedding=embedding,
                collection=collection,
                metadata=metadata,
            )

        logger.success(f"✅ [LOAD] 成功加载 {len(documents)} 个文档")
        return True

    except Exception as e:
        logger.error(f"❌ [LOAD] 文档加载失败: {e}\n{traceback.format_exc()}")
        return False


############################################################################################################
def search_documents(
    query: str,
    collection: str,
    embedding_model: SentenceTransformer,
    top_k: int = 5,
) -> Tuple[List[str], List[float]]:
    """
    执行语义搜索，查询公共知识库

    Args:
        query: 用户查询文本
        collection: 集合名称（用于隔离不同知识库，如游戏名）
        embedding_model: SentenceTransformer 嵌入模型实例
        top_k: 返回最相似的文档数量

    Returns:
        tuple: (检索到的文档列表, 相似度分数列表)
    """
    try:
        logger.info(f"🔍 [SEARCH] 执行语义搜索: '{query}'")

        query_vector = embedding_model.encode([query])[0].tolist()

        # threshold=0.0：始终返回 top_k 条结果，不做相关性过滤
        results = search_similar_documents(
            query_embedding=query_vector,
            limit=top_k,
            collection_filter=collection,
            similarity_threshold=0.0,
        )

        documents = [doc.content for doc, _ in results]
        similarity_scores = [score for _, score in results]

        logger.info(f"✅ [SEARCH] 搜索完成，找到 {len(documents)} 个相关文档")
        return documents, similarity_scores

    except Exception as e:
        logger.error(f"❌ [SEARCH] 语义搜索失败: {e}\n{traceback.format_exc()}")
        return [], []


############################################################################################################
def delete_collection(collection: str) -> int:
    """
    删除指定 collection 下的全部向量文档（开发/测试环境清理用）

    Args:
        collection: 集合名称

    Returns:
        int: 被删除的行数
    """
    db = SessionLocal()
    try:
        result = cast(
            CursorResult[Any],
            db.execute(
                text("DELETE FROM vector_documents WHERE collection = :collection"),
                {"collection": collection},
            ),
        )
        db.commit()
        return int(result.rowcount)
    finally:
        db.close()
