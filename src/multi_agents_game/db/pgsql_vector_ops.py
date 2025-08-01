"""
PostgreSQL + pgvector 向量操作工具集
提供向量存储、检索、相似度搜索等功能
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import json
from sqlalchemy import text
from loguru import logger

from .pgsql_client import SessionLocal
from .pgsql_vector import VectorDocumentDB, ConversationVectorDB, GameKnowledgeVectorDB


##################################################################################################################
# 向量文档操作
##################################################################################################################


def save_vector_document(
    content: str,
    embedding: List[float],
    title: Optional[str] = None,
    source: Optional[str] = None,
    doc_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> VectorDocumentDB:
    """
    保存文档及其向量嵌入到数据库

    参数:
        content: 文档内容
        embedding: 向量嵌入 (1536维)
        title: 文档标题
        source: 文档来源
        doc_type: 文档类型
        metadata: 元数据字典

    返回:
        VectorDocumentDB: 保存的文档对象
    """
    db = SessionLocal()
    try:
        # 验证向量维度
        if len(embedding) != 1536:
            raise ValueError(f"向量维度必须是1536，当前维度: {len(embedding)}")

        document = VectorDocumentDB(
            content=content,
            embedding=embedding,
            title=title,
            source=source,
            doc_type=doc_type,
            content_length=len(content),
            doc_metadata=json.dumps(metadata) if metadata else None,
        )

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


def search_similar_documents(
    query_embedding: List[float],
    limit: int = 10,
    doc_type_filter: Optional[str] = None,
    similarity_threshold: float = 0.3,
) -> List[Tuple[VectorDocumentDB, float]]:
    """
    基于向量相似度搜索文档

    参数:
        query_embedding: 查询向量
        limit: 返回结果数量限制
        doc_type_filter: 文档类型过滤
        similarity_threshold: 相似度阈值

    返回:
        List[Tuple[VectorDocumentDB, float]]: (文档对象, 相似度分数) 的列表
    """
    db = SessionLocal()
    try:
        if len(query_embedding) != 1536:
            raise ValueError(
                f"查询向量维度必须是1536，当前维度: {len(query_embedding)}"
            )

        # 构建SQL条件
        conditions = ["embedding IS NOT NULL"]
        # 将向量转换为PostgreSQL向量格式的字符串
        vector_str = "[" + ",".join(map(str, query_embedding)) + "]"
        params = {
            "query_vector": vector_str,
            "threshold": similarity_threshold,
            "limit": limit,
        }

        if doc_type_filter:
            conditions.append("doc_type = :doc_type_filter")
            params["doc_type_filter"] = doc_type_filter

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

        results = db.execute(text(sql), params).fetchall()

        # 转换结果
        documents_with_scores = []
        for row in results:
            doc = db.get(VectorDocumentDB, row.id)
            if doc:
                documents_with_scores.append((doc, float(row.similarity)))

        logger.info(f"🔍 找到 {len(documents_with_scores)} 个相似文档")
        return documents_with_scores

    except Exception as e:
        logger.error(f"❌ 向量搜索失败: {e}")
        raise e
    finally:
        db.close()


##################################################################################################################
# 对话向量操作
##################################################################################################################


def save_conversation_vector(
    message_content: str,
    embedding: List[float],
    sender: Optional[str] = None,
    receiver: Optional[str] = None,
    message_type: Optional[str] = None,
    game_session_id: Optional[UUID] = None,
) -> ConversationVectorDB:
    """
    保存对话消息及其向量嵌入

    参数:
        message_content: 消息内容
        embedding: 向量嵌入
        sender: 发送者
        receiver: 接收者
        message_type: 消息类型
        game_session_id: 游戏会话ID

    返回:
        ConversationVectorDB: 保存的对话对象
    """
    db = SessionLocal()
    try:
        if len(embedding) != 1536:
            raise ValueError(f"向量维度必须是1536，当前维度: {len(embedding)}")

        conversation = ConversationVectorDB(
            message_content=message_content,
            embedding=embedding,
            sender=sender,
            receiver=receiver,
            message_type=message_type,
            game_session_id=game_session_id,
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        logger.info(f"✅ 对话向量已保存: ID={conversation.id}")
        return conversation

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 保存对话向量失败: {e}")
        raise e
    finally:
        db.close()


def search_similar_conversations(
    query_embedding: List[float],
    limit: int = 10,
    game_session_id: Optional[UUID] = None,
    message_type_filter: Optional[str] = None,
    similarity_threshold: float = 0.5,
) -> List[Tuple[ConversationVectorDB, float]]:
    """
    搜索相似的对话消息

    参数:
        query_embedding: 查询向量
        limit: 返回结果数量限制
        game_session_id: 游戏会话ID过滤
        message_type_filter: 消息类型过滤
        similarity_threshold: 相似度阈值

    返回:
        List[Tuple[ConversationVectorDB, float]]: (对话对象, 相似度分数) 的列表
    """
    db = SessionLocal()
    try:
        if len(query_embedding) != 1536:
            raise ValueError(
                f"查询向量维度必须是1536，当前维度: {len(query_embedding)}"
            )

        # 构建SQL查询
        conditions = ["embedding IS NOT NULL"]
        # 将向量转换为PostgreSQL向量格式的字符串
        vector_str = "[" + ",".join(map(str, query_embedding)) + "]"
        params = {
            "query_vector": vector_str,  # 转换为字符串格式
            "threshold": similarity_threshold,
            "limit": limit,
        }

        if game_session_id:
            conditions.append("game_session_id = :game_session_id")
            params["game_session_id"] = str(game_session_id)

        if message_type_filter:
            conditions.append("message_type = :message_type_filter")
            params["message_type_filter"] = message_type_filter

        where_clause = " AND ".join(conditions)

        results = db.execute(
            text(
                f"""
                SELECT *, (1 - (embedding <=> :query_vector)) as similarity
                FROM conversation_vectors 
                WHERE {where_clause}
                    AND (1 - (embedding <=> :query_vector)) >= :threshold
                ORDER BY embedding <=> :query_vector
                LIMIT :limit
            """
            ),
            params,
        ).fetchall()

        # 转换结果
        conversations_with_scores = []
        for row in results:
            conv = db.get(ConversationVectorDB, row.id)
            if conv:
                conversations_with_scores.append((conv, float(row.similarity)))

        logger.info(f"🔍 找到 {len(conversations_with_scores)} 个相似对话")
        return conversations_with_scores

    except Exception as e:
        logger.error(f"❌ 对话向量搜索失败: {e}")
        raise e
    finally:
        db.close()


##################################################################################################################
# 游戏知识向量操作
##################################################################################################################


def save_game_knowledge_vector(
    knowledge_content: str,
    embedding: List[float],
    title: Optional[str] = None,
    knowledge_category: Optional[str] = None,
    game_type: Optional[str] = None,
    difficulty_level: Optional[int] = None,
    tags: Optional[List[str]] = None,
    priority: int = 0,
) -> GameKnowledgeVectorDB:
    """
    保存游戏知识及其向量嵌入

    参数:
        knowledge_content: 知识内容
        embedding: 向量嵌入
        title: 知识标题
        knowledge_category: 知识分类
        game_type: 游戏类型
        difficulty_level: 难度等级
        tags: 标签列表
        priority: 优先级

    返回:
        GameKnowledgeVectorDB: 保存的游戏知识对象
    """
    db = SessionLocal()
    try:
        if len(embedding) != 1536:
            raise ValueError(f"向量维度必须是1536，当前维度: {len(embedding)}")

        knowledge = GameKnowledgeVectorDB(
            knowledge_content=knowledge_content,
            embedding=embedding,
            title=title,
            knowledge_category=knowledge_category,
            game_type=game_type,
            difficulty_level=difficulty_level,
            tags=",".join(tags) if tags else None,
            priority=priority,
        )

        db.add(knowledge)
        db.commit()
        db.refresh(knowledge)

        logger.info(f"✅ 游戏知识向量已保存: ID={knowledge.id}")
        return knowledge

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 保存游戏知识向量失败: {e}")
        raise e
    finally:
        db.close()


def search_game_knowledge(
    query_embedding: List[float],
    limit: int = 10,
    game_type_filter: Optional[str] = None,
    knowledge_category_filter: Optional[str] = None,
    max_difficulty: Optional[int] = None,
    similarity_threshold: float = 0.4,
) -> List[Tuple[GameKnowledgeVectorDB, float]]:
    """
    搜索相关的游戏知识

    参数:
        query_embedding: 查询向量
        limit: 返回结果数量限制
        game_type_filter: 游戏类型过滤
        knowledge_category_filter: 知识分类过滤
        max_difficulty: 最大难度等级
        similarity_threshold: 相似度阈值

    返回:
        List[Tuple[GameKnowledgeVectorDB, float]]: (游戏知识对象, 相似度分数) 的列表
    """
    db = SessionLocal()
    try:
        if len(query_embedding) != 1536:
            raise ValueError(
                f"查询向量维度必须是1536，当前维度: {len(query_embedding)}"
            )

        # 构建SQL查询
        conditions = ["embedding IS NOT NULL"]
        # 将向量转换为PostgreSQL向量格式的字符串
        vector_str = "[" + ",".join(map(str, query_embedding)) + "]"
        params = {
            "query_vector": vector_str,  # 转换为字符串格式
            "threshold": similarity_threshold,
            "limit": limit,
        }

        if game_type_filter:
            conditions.append("game_type = :game_type_filter")
            params["game_type_filter"] = game_type_filter

        if knowledge_category_filter:
            conditions.append("knowledge_category = :knowledge_category_filter")
            params["knowledge_category_filter"] = knowledge_category_filter

        if max_difficulty is not None:
            conditions.append(
                "(difficulty_level IS NULL OR difficulty_level <= :max_difficulty)"
            )
            params["max_difficulty"] = max_difficulty

        where_clause = " AND ".join(conditions)

        results = db.execute(
            text(
                f"""
                SELECT *, (1 - (embedding <=> :query_vector)) as similarity
                FROM game_knowledge_vectors 
                WHERE {where_clause}
                    AND (1 - (embedding <=> :query_vector)) >= :threshold
                ORDER BY priority DESC, embedding <=> :query_vector
                LIMIT :limit
            """
            ),
            params,
        ).fetchall()

        # 转换结果
        knowledge_with_scores = []
        for row in results:
            knowledge = db.get(GameKnowledgeVectorDB, row.id)
            if knowledge:
                knowledge_with_scores.append((knowledge, float(row.similarity)))

        logger.info(f"🔍 找到 {len(knowledge_with_scores)} 个相关游戏知识")
        return knowledge_with_scores

    except Exception as e:
        logger.error(f"❌ 游戏知识搜索失败: {e}")
        raise e
    finally:
        db.close()


##################################################################################################################
# 辅助工具函数
##################################################################################################################


def get_database_vector_stats() -> Dict[str, Any]:
    """
    获取数据库中向量数据的统计信息

    返回:
        Dict[str, Any]: 包含各表向量数据统计的字典
    """
    db = SessionLocal()
    try:
        stats = {}

        # 向量文档统计
        doc_count = db.query(VectorDocumentDB).count()
        doc_with_vectors = (
            db.query(VectorDocumentDB)
            .filter(VectorDocumentDB.embedding.is_not(None))
            .count()
        )
        stats["vector_documents"] = {
            "total_count": doc_count,
            "with_embeddings": doc_with_vectors,
            "without_embeddings": doc_count - doc_with_vectors,
        }

        # 对话向量统计
        conv_count = db.query(ConversationVectorDB).count()
        conv_with_vectors = (
            db.query(ConversationVectorDB)
            .filter(ConversationVectorDB.embedding.is_not(None))
            .count()
        )
        stats["conversation_vectors"] = {
            "total_count": conv_count,
            "with_embeddings": conv_with_vectors,
            "without_embeddings": conv_count - conv_with_vectors,
        }

        # 游戏知识向量统计
        knowledge_count = db.query(GameKnowledgeVectorDB).count()
        knowledge_with_vectors = (
            db.query(GameKnowledgeVectorDB)
            .filter(GameKnowledgeVectorDB.embedding.is_not(None))
            .count()
        )
        stats["game_knowledge_vectors"] = {
            "total_count": knowledge_count,
            "with_embeddings": knowledge_with_vectors,
            "without_embeddings": knowledge_count - knowledge_with_vectors,
        }

        logger.info(f"📊 向量数据库统计: {stats}")
        return stats

    except Exception as e:
        logger.error(f"❌ 获取向量统计失败: {e}")
        raise e
    finally:
        db.close()


def cleanup_empty_embeddings() -> Dict[str, int]:
    """
    清理没有向量嵌入的记录

    返回:
        Dict[str, int]: 清理的记录数统计
    """
    db = SessionLocal()
    try:
        cleanup_stats = {}

        # 清理没有嵌入的文档
        deleted_docs = (
            db.query(VectorDocumentDB)
            .filter(VectorDocumentDB.embedding.is_(None))
            .delete()
        )
        cleanup_stats["deleted_documents"] = deleted_docs

        # 清理没有嵌入的对话
        deleted_convs = (
            db.query(ConversationVectorDB)
            .filter(ConversationVectorDB.embedding.is_(None))
            .delete()
        )
        cleanup_stats["deleted_conversations"] = deleted_convs

        # 清理没有嵌入的游戏知识
        deleted_knowledge = (
            db.query(GameKnowledgeVectorDB)
            .filter(GameKnowledgeVectorDB.embedding.is_(None))
            .delete()
        )
        cleanup_stats["deleted_knowledge"] = deleted_knowledge

        db.commit()

        logger.info(f"🧹 清理完成: {cleanup_stats}")
        return cleanup_stats

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 清理向量数据失败: {e}")
        raise e
    finally:
        db.close()
