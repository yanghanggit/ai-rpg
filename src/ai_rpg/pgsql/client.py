from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .config import postgresql_config
from .base import Base

############################################################################################################

# Create a SQLAlchemy engine using the PostgreSQL connection string from the configuration
engine = create_engine(postgresql_config.connection_string)

# 创建一个新的会话工厂，用于生成数据库会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


############################################################################################################
def pgsql_database_exists(database_name: str) -> bool:
    """
    判断数据库是否存在
    """

    # 构建连接到 postgres 数据库的连接字符串
    postgres_conn_str = (
        f"postgresql://{postgresql_config.user}@{postgresql_config.host}/postgres"
    )

    try:

        # 连接到 postgres 数据库
        postgres_engine = create_engine(postgres_conn_str)

        # 查询 pg_database 系统表以检查数据库是否存在
        with postgres_engine.connect() as conn:

            # 使用参数化查询以防止SQL注入
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": database_name},
            )

            # 检查查询结果是否为空，如果不为空，则数据库存在
            exists = result.fetchone() is not None

        # 关闭连接
        postgres_engine.dispose()
        return exists

    except Exception as e:
        logger.error(f"❌ 检查数据库是否存在时出错: {e}")
        raise


############################################################################################################
def pgsql_create_database(database_name: str) -> None:
    """
    创建数据库
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

        # 使用 with 语句确保连接在使用后被正确关闭
        with postgres_engine.connect() as conn:

            # 创建数据库
            conn.execute(text(f'CREATE DATABASE "{database_name}"'))
            logger.success(f"✅ 数据库 {database_name} 创建成功")

        # 关闭连接
        postgres_engine.dispose()

    except Exception as e:
        logger.error(f"❌ 创建数据库失败: {e}")
        raise


############################################################################################################
def pgsql_drop_database(database_name: str) -> None:
    """
    删除数据库
    注意：此操作不可逆，仅适用于开发环境
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

        # 关闭连接
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

        # 调用注册函数以确保所有模型都被注册
        register_all_models()

        # 确保所有表都已创建
        Base.metadata.create_all(bind=engine)
        logger.info("✅ 数据库表结构已确保存在")

    except Exception as e:
        logger.error(f"❌ 创建数据库表时出错: {e}")
        raise


############################################################################################################
