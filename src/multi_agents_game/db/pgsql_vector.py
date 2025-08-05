from datetime import datetime
from typing import Optional, List
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
