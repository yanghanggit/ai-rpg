#!/usr/bin/env python3
"""
开发环境初始化脚本

功能：
1. 初始化 PostgreSQL 数据库和测试用户
2. 创建演示游戏世界配置
3. 初始化 RAG 系统（全局知识库和角色私有知识库）
4. 生成服务器配置文件和 PM2 配置

使用方式：
    python setup_dev_environment.py

Author: yanghanggit
Date: 2025-07-30
"""

import os
from pathlib import Path
import sys
from typing import final
from pydantic import BaseModel

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
from loguru import logger

from ai_rpg.configuration import (
    ServerConfiguration,
    server_configuration,
)
from ai_rpg.game.config import BLUEPRINTS_DIR, DUNGEONS_DIR, GAME_1, GAME_2
from ai_rpg.demo import (
    create_hunter_mystic_blueprint,
    create_single_hunter_blueprint,
    create_mountain_beasts_dungeon,
    create_tiger_lair_dungeon,
    create_wild_boar_territory_dungeon,
    create_training_dungeon,
)
from ai_rpg.pgsql import (
    pgsql_create_database,
    pgsql_drop_database,
    pgsql_ensure_database_tables,
    postgresql_config,
)
from ai_rpg.pgsql.user_operations import has_user, save_user
from ai_rpg.demo import RPG_KNOWLEDGE_BASE
from ai_rpg.chroma import reset_client, get_custom_collection
from ai_rpg.rag import add_documents
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


########################################################################################################
########################################################################################################
########################################################################################################
def _save_demo_dungeons() -> None:
    """将演示地下城序列化为 JSON 文件，存入 DUNGEONS_DIR"""
    logger.info("🚀 保存演示地下城...")

    dungeons = [
        create_mountain_beasts_dungeon(),  # 山林妖兽狩猎副本
        create_tiger_lair_dungeon(),  # 山中虎巢穴副本
        create_wild_boar_territory_dungeon(),  # 野猪领地副本
        create_training_dungeon(),  # 猎人训练场副本
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

    blueprint_game1 = create_hunter_mystic_blueprint(GAME_1)
    path_game1 = BLUEPRINTS_DIR / f"{GAME_1}.json"
    path_game1.write_text(blueprint_game1.model_dump_json(indent=4), encoding="utf-8")
    logger.success(f"✅ {GAME_1}.json 已保存至 {path_game1.absolute()}")

    blueprint_game2 = create_single_hunter_blueprint(GAME_2)
    path_game2 = BLUEPRINTS_DIR / f"{GAME_2}.json"
    path_game2.write_text(blueprint_game2.model_dump_json(indent=4), encoding="utf-8")
    logger.success(f"✅ {GAME_2}.json 已保存至 {path_game2.absolute()}")


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
    为每个文件名对应的集合加载全局知识库 RPG_KNOWLEDGE_BASE。
    """
    logger.info("🚀 初始化RAG系统...")

    # 清空数据库
    logger.info("🧹 清空ChromaDB数据库...")
    reset_client()

    # 列出 BLUEPRINTS_DIR 下所有文件
    # blueprint_files = list(BLUEPRINTS_DIR.iterdir())
    game_names = [GAME_1, GAME_2]
    logger.info(f"📂 发现蓝图文件: {game_names}")

    if not game_names:
        logger.warning("⚠️ BLUEPRINTS_DIR 下没有蓝图文件，跳过RAG加载")
        logger.success("✅ RAG系统初始化完成!")
        return

    # 准备文档数据：将 Dict[str, List[str]] 展开为 flat lists（各游戏共用同一份）
    if not RPG_KNOWLEDGE_BASE or len(RPG_KNOWLEDGE_BASE) == 0:
        logger.warning("⚠️ 全局知识库 RPG_KNOWLEDGE_BASE 为空，跳过加载")
        logger.success("✅ RAG系统初始化完成!")
        return

    documents_list: list[str] = []
    metadatas_list: list[dict[str, str]] = []
    ids_list: list[str] = []

    doc_index = 0
    for category, docs in RPG_KNOWLEDGE_BASE.items():
        for doc in docs:
            documents_list.append(doc)
            metadatas_list.append({"category": category})
            ids_list.append(f"{category}_{doc_index}")
            doc_index += 1

    # 为每个蓝图文件名对应的集合分别加载知识库
    for game_name in game_names:
        logger.info(f"📚 为 {game_name} 加载公共知识库...")
        success = add_documents(
            collection=get_custom_collection(game_name),
            embedding_model=multilingual_model,
            documents=documents_list,
            metadatas=metadatas_list,
            ids=ids_list,
        )
        if not success:
            logger.error(f"❌ {game_name} 公共知识库加载失败!")
            raise Exception(f"{game_name} 公共知识库加载失败")
        logger.success(f"✅ {game_name} 公共知识库加载成功!")

    logger.success("✅ RAG系统初始化完成!")


########################################################################################################
########################################################################################################
########################################################################################################
def _generate_pm2_ecosystem_config(
    server_config: ServerConfiguration, target_directory: str = "."
) -> None:
    """
    生成 PM2 进程管理配置文件

    Args:
        server_config: 服务器配置对象
        target_directory: 目标目录路径，默认为当前目录
    """
    ecosystem_config_content = f"""module.exports = {{
  apps: [
    // 游戏服务器实例 - 端口 {server_config.game_server_port}
    {{
      name: 'game-server-{server_config.game_server_port}',
      script: 'uvicorn',
      args: 'scripts.run_game_server:app --host 0.0.0.0 --port {server_config.game_server_port}',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {{
        PYTHONPATH: `${{process.cwd()}}`,
        PORT: '{server_config.game_server_port}'
      }},
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/game-server-{server_config.game_server_port}.log',
      error_file: './logs/game-server-{server_config.game_server_port}-error.log',
      out_file: './logs/game-server-{server_config.game_server_port}-out.log',
      time: true
    }},
    // DeepSeek聊天服务器实例 - 端口 {server_config.deepseek_chat_server_port}
    {{
      name: 'deepseek-chat-server-{server_config.deepseek_chat_server_port}',
      script: 'uvicorn',
      args: 'scripts.run_deepseek_chat_server:app --host 0.0.0.0 --port {server_config.deepseek_chat_server_port}',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {{
        PYTHONPATH: `${{process.cwd()}}`,
        PORT: '{server_config.deepseek_chat_server_port}'
      }},
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/deepseek-chat-server-{server_config.deepseek_chat_server_port}.log',
      error_file: './logs/deepseek-chat-server-{server_config.deepseek_chat_server_port}-error.log',
      out_file: './logs/deepseek-chat-server-{server_config.deepseek_chat_server_port}-out.log',
      time: true
    }},
    // 图片生成服务器实例 - 端口 {server_config.replicate_image_generation_server_port}
    {{
      name: 'image-generation-server-{server_config.replicate_image_generation_server_port}',
      script: 'uvicorn',
      args: 'scripts.run_replicate_image_server:app --host 0.0.0.0 --port {server_config.replicate_image_generation_server_port}',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {{
        PYTHONPATH: `${{process.cwd()}}`,
        PORT: '{server_config.replicate_image_generation_server_port}'
      }},
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/image-generation-server-{server_config.replicate_image_generation_server_port}.log',
      error_file: './logs/image-generation-server-{server_config.replicate_image_generation_server_port}-error.log',
      out_file: './logs/image-generation-server-{server_config.replicate_image_generation_server_port}-out.log',
      time: true
    }}
  ]
}};
"""
    # 确保目标目录存在
    target_path = Path(target_directory)
    target_path.mkdir(parents=True, exist_ok=True)

    # 写入文件
    config_file_path = target_path / "ecosystem.config.js"
    config_file_path.write_text(ecosystem_config_content, encoding="utf-8")

    print(f"已生成 ecosystem.config.js 文件到: {config_file_path.absolute()}")


########################################################################################################
########################################################################################################
########################################################################################################
def _setup_server_settings() -> None:
    """生成服务器配置文件和 PM2 配置"""
    logger.info("🚀 构建服务器设置配置...")
    # 这里可以添加构建服务器设置配置的逻辑
    write_path = Path("server_configuration.json")
    write_path.write_text(
        server_configuration.model_dump_json(indent=4), encoding="utf-8"
    )
    logger.success("✅ 服务器设置配置构建完成")

    # 生成PM2生态系统配置
    _generate_pm2_ecosystem_config(server_configuration)


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

    # 保存演示地下城
    try:
        _save_demo_dungeons()
    except Exception as e:
        logger.error(f"❌ 保存演示地下城失败: {e}")

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

    # 服务器设置相关操作
    try:
        logger.info("🚀 设置服务器配置...")
        _setup_server_settings()
        logger.success("✅ 服务器配置设置完成")
    except Exception as e:
        logger.error(f"❌ 服务器配置设置失败: {e}")

    logger.info("🎉 开发环境初始化完成")


#######################################################################################################
# Main execution
if __name__ == "__main__":
    main()
