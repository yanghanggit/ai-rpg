from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ..config import DEFAULT_POSTGRES_CONFIG
from .pgsql_base import Base

############################################################################################################
engine = create_engine(DEFAULT_POSTGRES_CONFIG.connection_string)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


############################################################################################################
def pgsql_ensure_database_tables() -> None:
    """
    确保数据库表已创建
    这个函数在需要时才会被调用，避免导入时立即连接数据库
    """
    try:
        # 导入所有模型以确保它们被注册到Base.metadata中
        from .pgsql_vector_document import (
            VectorDocumentDB,
        )  # noqa: F401 # 确保向量表模型被注册

        Base.metadata.create_all(bind=engine)
        logger.info("✅ 数据库表结构已确保存在")
    except Exception as e:
        logger.error(f"❌ 创建数据库表时出错: {e}")
        raise


############################################################################################################
# 清库函数
def pgsql_reset_database() -> None:
    """
    清空数据库并重建表结构
    注意：该方法会删除所有数据，只适用于开发环境
    """
    try:
        # 导入所有模型以确保它们被注册到Base.metadata中
        from .pgsql_vector_document import (
            VectorDocumentDB,
        )  # noqa: F401 # 确保向量表模型被注册

        # 使用直接的SQL命令执行级联删除
        with engine.begin() as conn:
            # 确保pgvector扩展已启用
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            # 先禁用约束检查，然后删除所有表
            conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))

            # 获取所有表
            tables = conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            ).fetchall()

            # 对所有表使用CASCADE选项执行删除
            for table in tables:
                try:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table[0]}" CASCADE'))
                    logger.info(f"✅ 成功删除表: {table[0]}")
                except Exception as table_error:
                    logger.warning(f"⚠️ 删除表 {table[0]} 时出现警告: {table_error}")
                    # 尝试使用RESTRICT模式删除
                    try:
                        conn.execute(
                            text(f'DROP TABLE IF EXISTS "{table[0]}" RESTRICT')
                        )
                        logger.info(f"✅ 使用RESTRICT模式成功删除表: {table[0]}")
                    except Exception as restrict_error:
                        logger.error(f"❌ 无法删除表 {table[0]}: {restrict_error}")

        # 重新创建所有表（包括向量表）
        pgsql_ensure_database_tables()
        logger.warning("🔄 数据库表已被清除然后重建")

    except Exception as e:
        logger.error(f"❌ 重置数据库时发生错误: {e}")
        logger.info("💡 建议检查数据库用户权限和连接配置")
        raise


############################################################################################################
