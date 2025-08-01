from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from ..config.db_config import POSTGRES_DATABASE_URL
from .pgsql_object import Base

# 导入向量相关的表定义，确保它们被包含在元数据中
# from .pgsql_vector import VectorDocumentDB, ConversationVectorDB, GameKnowledgeVectorDB

############################################################################################################
engine = create_engine(POSTGRES_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
############################################################################################################
# 创建表
Base.metadata.create_all(bind=engine)


############################################################################################################
# 清库函数
def reset_database() -> None:
    """
    清空数据库并重建表结构
    注意：该方法会删除所有数据，只适用于开发环境
    """
    # 使用直接的SQL命令执行级联删除
    with engine.begin() as conn:
        # 确保pgvector扩展已启用
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # 先禁用约束检查，然后删除所有表
        conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))

        # 对所有表使用CASCADE选项执行删除
        tables = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).fetchall()

        for table in tables:
            conn.execute(text(f'DROP TABLE IF EXISTS "{table[0]}" CASCADE'))

    # 重新创建所有表
    Base.metadata.create_all(bind=engine)

    logger.warning("🔄 数据库表已被清除然后重建")


############################################################################################################
