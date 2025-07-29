import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import all required modules at the top
from loguru import logger
from sqlalchemy import text

from multi_agents_game.db.account import FAKE_USER
from multi_agents_game.db.pgsql_client import reset_database, SessionLocal
from multi_agents_game.db.pgsql_object import UserDB
from multi_agents_game.db.pgsql_user import has_user, save_user, get_user
from multi_agents_game.db.redis_client import (
    redis_flushall,
    redis_set,
    redis_get,
    redis_delete,
)
from multi_agents_game.db.mongodb_client import (
    mongodb_clear_database,
)


#######################################################################################################
def _test_redis() -> None:
    """
    测试 Redis 连接和基本操作

    使用简单的 set/get 操作验证 Redis 连接的可用性
    """
    test_key = "test_redis_connection"
    test_value = "hello_redis_2025"

    try:
        logger.info("🔍 开始测试 Redis 连接...")

        # 测试 SET 操作
        logger.info(f"📝 设置测试键值: {test_key} = {test_value}")
        redis_set(test_key, test_value)

        # 测试 GET 操作
        logger.info(f"📖 读取测试键值: {test_key}")
        retrieved_value = redis_get(test_key)

        # 验证结果
        if retrieved_value == test_value:
            logger.success(f"✅ Redis 连接测试成功! 读取到的值: {retrieved_value}")
        else:
            logger.error(
                f"❌ Redis 连接测试失败! 期望值: {test_value}, 实际值: {retrieved_value}"
            )
            return

        # 清理测试数据
        logger.info(f"🧹 清理测试数据: {test_key}")
        redis_delete(test_key)

        # 验证删除
        deleted_value = redis_get(test_key)
        if deleted_value is None:
            logger.success("✅ 测试数据清理成功!")
        else:
            logger.warning(f"⚠️ 测试数据清理异常，键值仍然存在: {deleted_value}")

        logger.success("🎉 Redis 连接和基本操作测试全部通过!")

    except Exception as e:
        logger.error(f"❌ Redis 连接测试失败: {e}")
        raise


#######################################################################################################
def _test_postgresql() -> None:
    """
    测试 PostgreSQL 连接和基本操作

    使用简单的用户 CRUD 操作验证 PostgreSQL 连接的可用性
    """
    test_username = "test_postgresql_connection"
    test_password = "test_password_2025"
    test_display_name = "Test User PostgreSQL"

    try:
        logger.info("🔍 开始测试 PostgreSQL 连接...")

        # 1. 测试数据库连接
        logger.info("📡 测试数据库连接...")
        db = SessionLocal()
        try:
            # 执行简单查询验证连接
            result = db.execute(text("SELECT 1 as test_connection")).fetchone()
            if result and result[0] == 1:
                logger.success("✅ PostgreSQL 数据库连接成功!")
            else:
                logger.error("❌ PostgreSQL 数据库连接验证失败!")
                return
        finally:
            db.close()

        # 2. 测试用户创建操作
        logger.info(f"👤 创建测试用户: {test_username}")
        created_user = save_user(
            username=test_username,
            hashed_password=test_password,
            display_name=test_display_name,
        )

        if created_user and created_user.username == test_username:
            logger.success(f"✅ 用户创建成功! 用户ID: {created_user.id}")
        else:
            logger.error("❌ 用户创建失败!")
            return

        # 3. 测试用户查询操作
        logger.info(f"🔍 查询测试用户: {test_username}")
        retrieved_user = get_user(test_username)

        if (
            retrieved_user
            and retrieved_user.username == test_username
            and retrieved_user.hashed_password == test_password
            and retrieved_user.display_name == test_display_name
        ):
            logger.success(f"✅ 用户查询成功! 显示名: {retrieved_user.display_name}")
        else:
            logger.error("❌ 用户查询失败或数据不匹配!")
            return

        # 4. 测试用户存在性检查
        logger.info(f"🔎 检查用户是否存在: {test_username}")
        user_exists = has_user(test_username)

        if user_exists:
            logger.success("✅ 用户存在性检查通过!")
        else:
            logger.error("❌ 用户存在性检查失败!")
            return

        # 5. 清理测试数据
        logger.info(f"🧹 清理测试数据: {test_username}")
        db = SessionLocal()
        try:
            test_user = db.query(UserDB).filter_by(username=test_username).first()
            if test_user:
                db.delete(test_user)
                db.commit()
                logger.success("✅ 测试数据清理成功!")
            else:
                logger.warning("⚠️ 未找到要清理的测试用户")
        except Exception as cleanup_error:
            db.rollback()
            logger.error(f"❌ 测试数据清理失败: {cleanup_error}")
        finally:
            db.close()

        # 6. 验证清理结果
        logger.info(f"🔍 验证测试数据已清理: {test_username}")
        user_still_exists = has_user(test_username)

        if not user_still_exists:
            logger.success("✅ 测试数据清理验证通过!")
        else:
            logger.warning("⚠️ 测试数据清理验证异常，用户仍然存在")

        logger.success("🎉 PostgreSQL 连接和基本操作测试全部通过!")

    except Exception as e:
        logger.error(f"❌ PostgreSQL 连接测试失败: {e}")
        raise


#######################################################################################################
# Clear database development utility
def main() -> None:
    logger.info("🚀 首先测试 Redis 连接...")
    _test_redis()

    # 测试 PostgreSQL 连接
    logger.info("🚀 测试 PostgreSQL 连接...")
    _test_postgresql()

    # 清空 Redis 数据库
    logger.info("🚀 清空 Redis 数据库...")
    redis_flushall()

    # 清空 PostgreSQL 数据库
    logger.info("🚀 清空 PostgreSQL 数据库...")
    reset_database()

    # 清空 MongoDB 数据库
    logger.info("🚀 清空 MongoDB 数据库...")
    mongodb_clear_database()

    # 检查并保存测试用户
    logger.info("🚀 检查并保存测试用户...")
    if not has_user(FAKE_USER.username):
        save_user(
            username=FAKE_USER.username,
            hashed_password=FAKE_USER.hashed_password,
            display_name=FAKE_USER.display_name,
        )
        logger.warning(f"测试用户 {FAKE_USER.username} 已创建")


#######################################################################################################
# Main execution
if __name__ == "__main__":
    main()
