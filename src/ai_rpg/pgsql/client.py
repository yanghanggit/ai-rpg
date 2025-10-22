from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .config import postgresql_config
from .base import Base

############################################################################################################
engine = create_engine(postgresql_config.connection_string)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


############################################################################################################
def pgsql_database_exists(database_name: str) -> bool:
    """
    判断数据库是否存在

    Args:
        database_name: 数据库名称

    Returns:
        bool: 数据库存在返回 True，否则返回 False
    """
    # 构建连接到 postgres 数据库的连接字符串
    postgres_conn_str = (
        f"postgresql://{postgresql_config.user}@{postgresql_config.host}/postgres"
    )

    try:
        postgres_engine = create_engine(postgres_conn_str)
        with postgres_engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": database_name},
            )
            exists = result.fetchone() is not None

        postgres_engine.dispose()
        return exists

    except Exception as e:
        logger.error(f"❌ 检查数据库是否存在时出错: {e}")
        raise


############################################################################################################
def pgsql_create_database(database_name: str) -> None:
    """
    创建数据库

    Args:
        database_name: 数据库名称
    """
    # 先检查数据库是否已存在
    if pgsql_database_exists(database_name):
        logger.info(f"✅ 数据库 {database_name} 已存在，跳过创建")
        return

    # 构建连接到 postgres 数据库的连接字符串
    postgres_conn_str = (
        f"postgresql://{postgresql_config.user}@{postgresql_config.host}/postgres"
    )

    try:
        # 连接到 postgres 数据库
        postgres_engine = create_engine(
            postgres_conn_str,
            isolation_level="AUTOCOMMIT",  # CREATE DATABASE 需要 AUTOCOMMIT 模式
        )

        with postgres_engine.connect() as conn:
            # 创建数据库
            conn.execute(text(f'CREATE DATABASE "{database_name}"'))
            logger.success(f"✅ 数据库 {database_name} 创建成功")

        postgres_engine.dispose()

    except Exception as e:
        logger.error(f"❌ 创建数据库失败: {e}")
        raise


############################################################################################################
def pgsql_drop_database(database_name: str) -> None:
    """
    删除数据库
    注意：此操作不可逆，仅适用于开发环境

    Args:
        database_name: 数据库名称
    """
    # 先检查数据库是否存在
    if not pgsql_database_exists(database_name):
        logger.info(f"ℹ️ 数据库 {database_name} 不存在，无需删除")
        return

    # 构建连接到 postgres 数据库的连接字符串
    postgres_conn_str = (
        f"postgresql://{postgresql_config.user}@{postgresql_config.host}/postgres"
    )

    try:
        # 连接到 postgres 数据库
        postgres_engine = create_engine(
            postgres_conn_str,
            isolation_level="AUTOCOMMIT",  # DROP DATABASE 需要 AUTOCOMMIT 模式
        )

        with postgres_engine.connect() as conn:
            # 强制断开所有连接到目标数据库的会话
            conn.execute(
                text(
                    f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = :dbname
                    AND pid <> pg_backend_pid()
                    """
                ),
                {"dbname": database_name},
            )

            # 删除数据库
            conn.execute(text(f'DROP DATABASE "{database_name}"'))
            logger.warning(f"🗑️ 数据库 {database_name} 已删除")

        postgres_engine.dispose()

    except Exception as e:
        logger.error(f"❌ 删除数据库失败: {e}")
        raise


############################################################################################################
def pgsql_ensure_database_tables() -> None:
    """
    确保数据库表已创建
    这个函数在需要时才会被调用，避免导入时立即连接数据库
    """
    try:
        # 先确保 pgvector 扩展已启用
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("✅ pgvector 扩展已确保启用")

        # 导入模型注册模块以确保所有模型被注册到Base.metadata中
        from .model_registry import register_all_models

        register_all_models()

        Base.metadata.create_all(bind=engine)
        logger.info("✅ 数据库表结构已确保存在")
    except Exception as e:
        logger.error(f"❌ 创建数据库表时出错: {e}")
        raise


############################################################################################################
