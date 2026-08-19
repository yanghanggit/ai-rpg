"""
PostgreSQL + pgvector 向量文档操作函数
提供向量存储、检索、相似度搜索等功能
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger
from sqlalchemy import text
from .client import SessionLocal
from .vector_document import VectorDocumentDB, EMBEDDING_DIMENSION


##################################################################################################################
# 向量文档操作
##################################################################################################################


def save_vector_document(
    content: str,
    embedding: List[float],
    collection: str,
    title: Optional[str] = None,
    source: Optional[str] = None,
    doc_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> VectorDocumentDB:
    """
    保存文档及其向量嵌入到数据库
    """

    db = SessionLocal()
    try:

        # 验证向量维度
        if len(embedding) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"向量维度必须是{EMBEDDING_DIMENSION}，当前维度: {len(embedding)}"
            )

        # 创建 VectorDocumentDB 实例
        document = VectorDocumentDB(
            content=content,
            embedding=embedding,
            collection=collection,
            title=title,
            source=source,
            doc_type=doc_type,
            content_length=len(content),
            doc_metadata=json.dumps(metadata) if metadata else None,
        )

        # 将文档添加到数据库会话并提交事务
        db.add(document)
        db.commit()
        db.refresh(document)

        logger.info(f"✅ 向量文档已保存: ID={document.id}, 内容长度={len(content)}")
        return document

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 保存向量文档失败: {e}")
        raise e

    finally:

        db.close()


###################################################################################################################
def search_similar_documents(
    query_embedding: List[float],
    limit: int = 10,
    collection_filter: Optional[str] = None,
    doc_type_filter: Optional[str] = None,
    similarity_threshold: float = 0.3,
) -> List[Tuple[VectorDocumentDB, float]]:
    """
    基于向量相似度搜索文档
    """

    db = SessionLocal()
    try:

        # 验证查询向量维度
        if len(query_embedding) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"查询向量维度必须是{EMBEDDING_DIMENSION}，当前维度: {len(query_embedding)}"
            )

        # 构建SQL条件
        conditions = ["embedding IS NOT NULL"]

        # 将向量转换为PostgreSQL向量格式的字符串
        vector_str = "[" + ",".join(map(str, query_embedding)) + "]"

        # 构建参数字典
        params = {
            "query_vector": vector_str,
            "threshold": similarity_threshold,
            "limit": limit,
        }

        # 如果提供了集合过滤器，则添加到条件中
        if collection_filter:
            conditions.append("collection = :collection_filter")
            params["collection_filter"] = collection_filter

        # 如果提供了文档类型过滤器，则添加到条件中
        if doc_type_filter:
            conditions.append("doc_type = :doc_type_filter")
            params["doc_type_filter"] = doc_type_filter

        # 构建WHERE子句
        where_clause = " AND ".join(conditions)

        # 直接使用原生SQL进行向量搜索
        sql = f"""
            SELECT *, (1 - (embedding <=> :query_vector)) as similarity
            FROM vector_documents 
            WHERE {where_clause}
                AND (1 - (embedding <=> :query_vector)) >= :threshold
            ORDER BY embedding <=> :query_vector
            LIMIT :limit
        """

        # 执行SQL查询并获取结果
        results = db.execute(text(sql), params).fetchall()

        # 转换结果
        documents_with_scores = []
        for row in results:
            doc = db.get(VectorDocumentDB, row.id)
            if doc:
                documents_with_scores.append((doc, float(row.similarity)))

        # 记录日志
        logger.info(f"🔍 找到 {len(documents_with_scores)} 个相似文档")
        return documents_with_scores

    except Exception as e:
        logger.error(f"❌ 向量搜索失败: {e}")
        raise e
    finally:
        db.close()
