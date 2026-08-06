#!/usr/bin/env python3
"""
开发环境初始化脚本
"""

import os
import sys
from typing import Final, final, List, Dict
from pydantic import BaseModel

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
from loguru import logger
from ai_rpg.game.config import BLUEPRINTS_DIR, DUNGEONS_DIR
from ai_rpg.models import Blueprint
from demo import (
    create_ruins_blueprint,
    create_shrine_ruins_dungeon,
)
from ai_rpg.pgsql import (
    pgsql_create_database,
    pgsql_drop_database,
    pgsql_ensure_database_tables,
    postgresql_config,
)
from ai_rpg.pgsql.user_operations import has_user, save_user
from ai_rpg.chroma import reset_client, get_custom_collection, add_documents
from ai_rpg.embedding_model.sentence_transformer import multilingual_model


#######################################################################################################
@final
class UserAccount(BaseModel):
    username: str
    hashed_password: str
    display_name: str


########################################################################################################
########################################################################################################
########################################################################################################
FAKE_USER = UserAccount(
    username="yanghangethan@gmail.com",
    hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # 明文是 secret
    display_name="yh",
)

###########################################################################################################################################
# 默认游戏名称
GAME_1: Final[str] = (
    "Game1"  # unity 客户端目前是一定会链接到这个游戏的，所以这个名字暂时不能改。
)


########################################################################################################
########################################################################################################
########################################################################################################
def _save_demo_dungeons() -> None:
    """将演示副本序列化为 JSON 文件，存入 DUNGEONS_DIR"""
    logger.info("🚀 保存演示副本...")

    dungeons = [
        # create_mountain_beasts_dungeon(),  # 山林妖兽狩猎副本
        # create_tiger_lair_dungeon(),  # 山中虎巢穴副本
        create_shrine_ruins_dungeon(),  # 坍塌庙祠副本
        # create_training_dungeon(),  # 猎人训练场副本
    ]

    for dungeon in dungeons:
        path = DUNGEONS_DIR / f"{dungeon.name}.json"
        path.write_text(dungeon.model_dump_json(indent=4), encoding="utf-8")
        logger.success(f"✅ {dungeon.name}.json 已保存至 {path.absolute()}")


########################################################################################################
########################################################################################################
########################################################################################################
def _save_demo_blueprints() -> None:
    """将演示游戏世界蓝图序列化为 JSON 文件，存入 BLUEPRINTS_DIR"""
    logger.info("🚀 保存演示游戏蓝图...")

    blueprint_game1 = create_ruins_blueprint(GAME_1)
    path_game1 = BLUEPRINTS_DIR / f"{GAME_1}.json"
    path_game1.write_text(blueprint_game1.model_dump_json(indent=4), encoding="utf-8")
    logger.success(f"✅ {GAME_1}.json 已保存至 {path_game1.absolute()}")


########################################################################################################
########################################################################################################
########################################################################################################
def _pgsql_setup_test_user() -> None:
    """检查并创建测试用户账号"""
    logger.info("🚀 检查并保存测试用户...")
    if not has_user(FAKE_USER.username):
        save_user(
            username=FAKE_USER.username,
            hashed_password=FAKE_USER.hashed_password,
            display_name=FAKE_USER.display_name,
        )
        logger.info(f"测试用户 {FAKE_USER.username} 已创建")
    else:
        logger.info(f"测试用户 {FAKE_USER.username} 已存在，跳过创建")


########################################################################################################
########################################################################################################
########################################################################################################
def _setup_chromadb_rag_environment() -> None:
    """
    初始化 RAG 系统

    清空 ChromaDB 数据库，遍历 BLUEPRINTS_DIR 下所有蓝图文件，
    读取每个蓝图实例，使用其 knowledge_base 字段为对应的集合加载知识库。
    """
    logger.info("🚀 初始化RAG系统...")

    # 清空数据库
    logger.info("🧹 清空ChromaDB数据库...")
    reset_client()

    # 读取 BLUEPRINTS_DIR 下所有蓝图文件为 Blueprint 实例
    blueprints = [
        Blueprint.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(BLUEPRINTS_DIR.glob("*.json"))
    ]
    logger.info(f"📂 发现蓝图文件: {[blueprint.name for blueprint in blueprints]}")

    if not blueprints:
        logger.warning("⚠️ BLUEPRINTS_DIR 下没有蓝图文件，跳过RAG加载")
        logger.success("✅ RAG系统初始化完成!")
        return

    # 为每个蓝图分别加载其自带的知识库
    for blueprint in blueprints:
        if not blueprint.knowledge_base:
            logger.warning(f"⚠️ 蓝图 {blueprint.name} 的知识库为空，跳过加载")
            continue

        # 准备文档数据：将 Dict[str, List[str]] 展开为 flat lists
        documents_list: List[str] = []
        metadatas_list: List[Dict[str, str]] = []
        ids_list: List[str] = []

        doc_index = 0
        for category, docs in blueprint.knowledge_base.items():
            for doc in docs:
                documents_list.append(doc)
                metadatas_list.append({"category": category})
                ids_list.append(f"{category}_{doc_index}")
                doc_index += 1

        logger.info(f"📚 为 {blueprint.name} 加载知识库...")
        success = add_documents(
            collection=get_custom_collection(blueprint.name),
            embedding_model=multilingual_model,
            documents=documents_list,
            metadatas=metadatas_list,
            ids=ids_list,
        )
        if not success:
            logger.error(f"❌ {blueprint.name} 知识库加载失败!")
            raise Exception(f"{blueprint.name} 知识库加载失败")
        logger.success(f"✅ {blueprint.name} 知识库加载成功!")

    logger.success("✅ RAG系统初始化完成!")


########################################################################################################
########################################################################################################
########################################################################################################
def main() -> None:
    """主函数：执行完整的开发环境初始化流程"""
    logger.info("🚀 开始初始化开发环境...")

    # 保存演示游戏蓝图
    try:
        _save_demo_blueprints()
    except Exception as e:
        logger.error(f"❌ 保存演示游戏蓝图失败: {e}")

    # 保存演示副本
    try:
        _save_demo_dungeons()
    except Exception as e:
        logger.error(f"❌ 保存演示副本失败: {e}")

    # PostgreSQL 相关操作
    try:
        logger.info("�️ 删除旧数据库（如果存在）...")
        pgsql_drop_database(postgresql_config.database)

        logger.info("📦 创建新数据库...")
        pgsql_create_database(postgresql_config.database)

        logger.info("📋 创建数据库表结构...")
        pgsql_ensure_database_tables()

        logger.info("� 设置PostgreSQL测试用户...")
        _pgsql_setup_test_user()

        logger.success("✅ PostgreSQL 初始化完成")
    except Exception as e:
        logger.error(f"❌ PostgreSQL 初始化失败: {e}")

    # RAG 系统相关操作
    try:
        logger.info("🚀 初始化RAG系统...")
        _setup_chromadb_rag_environment()
        logger.success("✅ RAG 系统初始化完成")
    except Exception as e:
        logger.error(f"❌ RAG 系统初始化失败: {e}")

    logger.info("🎉 开发环境初始化完成")


#######################################################################################################
# Main execution
if __name__ == "__main__":
    main()
