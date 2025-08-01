from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlalchemy import DateTime, String, Text, Integer, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from .pgsql_object import UUIDBase


class VectorDocumentDB(UUIDBase):
    """向量文档存储表 - 用于RAG功能的文档向量化存储"""

    __tablename__ = "vector_documents"

    # 文档内容
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 文档标题/摘要
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # 文档来源/路径
    source: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # 文档类型/分类
    doc_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # 向量嵌入 (假设使用1536维度的向量，如OpenAI的text-embedding-ada-002)
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536), nullable=True
    )

    # 文档大小/字符数
    content_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 元数据字段（重命名以避免与SQLAlchemy的metadata冲突）
    doc_metadata: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON字符串存储额外信息

    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 更新时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 为向量字段创建索引以优化相似度搜索
    __table_args__ = (
        Index(
            "ix_vector_documents_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
        ),
        Index("ix_vector_documents_doc_type", "doc_type"),
        Index("ix_vector_documents_source", "source"),
    )


class ConversationVectorDB(UUIDBase):
    """对话向量存储表 - 用于对话历史的向量化存储和检索"""

    __tablename__ = "conversation_vectors"

    # 对话内容
    message_content: Mapped[str] = mapped_column(Text, nullable=False)

    # 发送者信息
    sender: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 接收者信息
    receiver: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 对话类型 (user_message, assistant_message, system_message等)
    message_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # 游戏会话ID
    game_session_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)

    # 向量嵌入
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536), nullable=True
    )

    # 对话时间戳
    message_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 更新时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 索引优化
    __table_args__ = (
        Index(
            "ix_conversation_vectors_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
        ),
        Index("ix_conversation_vectors_game_session", "game_session_id"),
        Index("ix_conversation_vectors_message_type", "message_type"),
    )


class GameKnowledgeVectorDB(UUIDBase):
    """游戏知识向量存储表 - 用于游戏规则、策略等知识的向量化存储"""

    __tablename__ = "game_knowledge_vectors"

    # 知识内容
    knowledge_content: Mapped[str] = mapped_column(Text, nullable=False)

    # 知识标题
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # 知识分类 (game_rules, strategies, tips, faq等)
    knowledge_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # 适用的游戏类型
    game_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # 难度等级
    difficulty_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 向量嵌入
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536), nullable=True
    )

    # 标签 (可以包含多个标签，用逗号分隔)
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # 优先级
    priority: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)

    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 更新时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 索引优化
    __table_args__ = (
        Index(
            "ix_game_knowledge_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
        ),
        Index("ix_game_knowledge_category", "knowledge_category"),
        Index("ix_game_knowledge_game_type", "game_type"),
        Index("ix_game_knowledge_priority", "priority"),
    )
