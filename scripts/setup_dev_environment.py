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
from ai_rpg.game.config import GAME_1
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


#######################################################################################################
FAKE_USER = UserAccount(
    username="yanghangethan@gmail.com",
    hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # 明文是 secret
    display_name="yh",
)


#######################################################################################################
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


#######################################################################################################
# def _save_demo_world_blueprint(game_name: str) -> None:
#     """创建并保存演示游戏世界配置文件"""
#     logger.info("🚀 创建演示游戏世界...")

#     world_blueprint = create_hunter_mystic_blueprint(game_name)
#     write_blueprint_path = BLUEPRINTS_DIR / f"{world_blueprint.name}.json"
#     write_blueprint_path.write_text(
#         world_blueprint.model_dump_json(indent=2),
#         encoding="utf-8",
#     )


#######################################################################################################
def _setup_chromadb_rag_environment(game_name: str) -> None:
    """
    初始化 RAG 系统

    清空 ChromaDB 数据库，加载全局知识库和角色私有知识库

    Args:
        game_name: 游戏名称
    """
    logger.info("🚀 初始化RAG系统...")

    # 清空数据库
    logger.info("🧹 清空ChromaDB数据库...")
    reset_client()

    # 加载全局知识库
    if not RPG_KNOWLEDGE_BASE or len(RPG_KNOWLEDGE_BASE) == 0:
        logger.warning("⚠️ 全局知识库 RPG_KNOWLEDGE_BASE 为空，跳过加载")
    else:
        logger.info("📚 加载公共知识库...")

        # 准备文档数据：将 Dict[str, List[str]] 展开为 flat lists
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

        # 调用 add_documents
        success = add_documents(
            collection=get_custom_collection(game_name),
            embedding_model=multilingual_model,
            documents=documents_list,
            metadatas=metadatas_list,
            ids=ids_list,
        )

        if not success:
            logger.error("❌ 公共知识库加载失败!")
            raise Exception("公共知识库加载失败")

        logger.success("✅ 公共知识库加载成功!")

    # 加载角色私有知识库
    # logger.info("🔐 开始加载角色私有知识库...")
    # world_blueprint_path = WORLD_BLUEPRINT_DIR / f"{game_name}.json"

    # if not world_blueprint_path.exists():
    #     logger.warning(f"⚠️ 世界配置文件不存在: {world_blueprint_path}")
    #     logger.warning("⚠️ 跳过私有知识库加载")
    # else:
    #     # 读取世界配置
    #     world_blueprint = Blueprint.model_validate_json(
    #         world_blueprint_path.read_text(encoding="utf-8")
    #     )

    #     # 统计加载情况
    #     loaded_count = 0
    #     skipped_count = 0

    #     # 遍历所有角色，加载私有知识
    #     for actor in world_blueprint.actors:
    #         # 直接从Actor对象的private_knowledge字段读取知识
    #         if actor.private_knowledge and len(actor.private_knowledge) > 0:
    #             logger.info(
    #                 f"🔐 为 {actor.name} 加载 {len(actor.private_knowledge)} 条私有知识"
    #             )

    #             success = add_documents(
    #                 collection=get_default_collection(),
    #                 embedding_model=multilingual_model,
    #                 documents=actor.private_knowledge,
    #                 owner=f"{game_name}.{actor.name}",  # 使用游戏名前缀实现知识隔离
    #             )

    #             if success:
    #                 loaded_count += 1
    #             else:
    #                 logger.error(f"❌ {actor.name} 的私有知识加载失败")
    #         else:
    #             skipped_count += 1
    #             logger.debug(f"跳过 {actor.name}（无私有知识）")

    #     logger.success(
    #         f"✅ 私有知识库加载完成! 成功: {loaded_count}, 跳过: {skipped_count}"
    #     )

    logger.success("✅ RAG系统初始化完成!")


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


#######################################################################################################
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


#######################################################################################################
def main() -> None:
    """主函数：执行完整的开发环境初始化流程"""
    logger.info("🚀 开始初始化开发环境...")

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

    # 创建演示游戏世界
    # try:
    #     logger.info("🚀 创建M演示游戏世界...")
    #     _save_demo_world_blueprint(GAME_1)
    # except Exception as e:
    #     logger.error(f"❌ 创建MongoDB演示游戏世界失败: {e}")

    # RAG 系统相关操作
    try:
        logger.info("🚀 初始化RAG系统...")
        _setup_chromadb_rag_environment(GAME_1)
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
