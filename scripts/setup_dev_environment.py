#!/usr/bin/env python3
"""
Development Environment Setup Script

This script sets up and initializes the development environment for the multi-agents game framework.

Main functions:
1. Test database connections (Redis, PostgreSQL, MongoDB)
2. Clear and reset all databases
3. Initialize development environment with test data
4. Create and store demo game world

Usage:
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
from ai_rpg.game.config import GLOBAL_TCG_GAME_NAME, WORLD_BOOT_DIR
from ai_rpg.pgsql import (
    pgsql_create_database,
    pgsql_drop_database,
    pgsql_ensure_database_tables,
    postgresql_config,
)
from ai_rpg.pgsql.user_operations import has_user, save_user
from ai_rpg.demo import create_demo_game_world_boot3


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
    """
    检查并保存测试用户

    如果测试用户不存在，则创建一个用于开发测试的用户账号
    """
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
def _save_demo_world_boot(game_name: str) -> None:
    """ """
    logger.info("🚀 创建演示游戏世界...")

    try:
        # world_boot = create_demo_game_world_boot1(GLOBAL_TCG_GAME_NAME)
        world_boot = create_demo_game_world_boot3(game_name)
        write_boot_path = WORLD_BOOT_DIR / f"{world_boot.name}.json"
        write_boot_path.write_text(
            world_boot.model_dump_json(indent=2),
            encoding="utf-8",
        )

    except Exception as e:
        logger.error(f"❌ 演示游戏世界 MongoDB 操作失败: {e}")
        raise


#######################################################################################################
def _setup_chromadb_rag_environment() -> None:
    """
    初始化RAG系统

    清理现有的ChromaDB数据，然后使用正式的知识库数据重新初始化RAG系统，
    包括向量数据库的设置和知识库数据的加载
    """
    logger.info("🚀 初始化RAG系统...")

    # 导入必要的模块
    from ai_rpg.chroma import get_default_collection, reset_client
    from ai_rpg.rag import load_knowledge_base_to_vector_db
    from ai_rpg.embedding_model.sentence_transformer import (
        multilingual_model,
    )
    from ai_rpg.demo.campaign_setting import FANTASY_WORLD_RPG_KNOWLEDGE_BASE

    try:

        # 新的测试
        logger.info("🧹 清空ChromaDB数据库...")
        reset_client()

        # 使用正式知识库数据初始化RAG系统
        # logger.info("📚 加载艾尔法尼亚世界知识库...")
        success = load_knowledge_base_to_vector_db(
            FANTASY_WORLD_RPG_KNOWLEDGE_BASE,
            multilingual_model,
            get_default_collection(),
        )

        if success:
            logger.success("✅ RAG系统初始化成功!")
            # logger.info(f"  - 知识库类别数量: {len(FANTASY_WORLD_RPG_KNOWLEDGE_BASE)}")

            # # 统计总文档数量
            # total_documents = sum(
            #     len(docs) for docs in FANTASY_WORLD_RPG_KNOWLEDGE_BASE.values()
            # )
            # logger.info(f"  - 总文档数量: {total_documents}")

            # 显示知识库类别
            # categories = list(FANTASY_WORLD_RPG_KNOWLEDGE_BASE.keys())
            # logger.info(f"  - 知识库类别: {', '.join(categories)}")

        else:
            logger.error("❌ RAG系统初始化失败!")
            raise Exception("RAG系统初始化返回失败状态")

    except ImportError as e:
        logger.error(f"❌ RAG系统模块导入失败: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ RAG系统初始化过程中发生错误: {e}")
        raise


def _generate_pm2_ecosystem_config(
    server_config: ServerConfiguration, target_directory: str = "."
) -> None:
    """
    根据 ServerSettings 配置生成 ecosystem.config.js 文件

    Args:
        target_directory: 目标目录路径，默认为当前目录

    确保在项目根目录

    启动所有服务
    pm2 start ecosystem.config.js

    查看状态
    pm2 status

    停止所有服务
    pm2 delete ecosystem.config.js
    """
    ecosystem_config_content = f"""module.exports = {{
  apps: [
    // 游戏服务器实例 - 端口 {server_config.game_server_port}
    {{
      name: 'game-server-{server_config.game_server_port}',
      script: 'uvicorn',
      args: 'scripts.run_tcg_game_server:app --host 0.0.0.0 --port {server_config.game_server_port}',
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
    // 图片生成服务器实例 - 端口 {server_config.image_generation_server_port}
    {{
      name: 'image-generation-server-{server_config.image_generation_server_port}',
      script: 'uvicorn',
      args: 'scripts.run_image_generation_server:app --host 0.0.0.0 --port {server_config.image_generation_server_port}',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {{
        PYTHONPATH: `${{process.cwd()}}`,
        PORT: '{server_config.image_generation_server_port}'
      }},
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/image-generation-server-{server_config.image_generation_server_port}.log',
      error_file: './logs/image-generation-server-{server_config.image_generation_server_port}-error.log',
      out_file: './logs/image-generation-server-{server_config.image_generation_server_port}-out.log',
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
    """
    构建服务器设置配置
    """
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

    # 创建演示游戏世界
    try:
        logger.info("🚀 创建M演示游戏世界...")
        _save_demo_world_boot(GLOBAL_TCG_GAME_NAME)
    except Exception as e:
        logger.error(f"❌ 创建MongoDB演示游戏世界失败: {e}")

    logger.info("🎉 开发环境初始化完成")


#######################################################################################################
# Main execution
if __name__ == "__main__":
    main()
