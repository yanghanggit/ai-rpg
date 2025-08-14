#!/usr/bin/env python3
"""
统一聊天系统启动脚本

功能：
1. 智能路由：自动检测查询类型并选择最佳处理模式
2. 直接对话：一般性聊天使用DeepSeek直接回答
3. RAG增强：艾尔法尼亚世界相关问题使用知识库增强
4. 无缝切换：用户无需手动选择模式

使用方法：
    python scripts/run_unified_chat.py

或者在项目根目录下：
    python -m scripts.run_unified_chat
"""

import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from loguru import logger
from multi_agents_game.chat_services.chat_deepseek_graph_complex import main


def run_unified_chat_system() -> None:
    """
    启动统一聊天系统

    功能特性：
    1. 🚦 智能路由：基于关键词的自动模式选择
    2. 💬 直接对话：快速响应一般性问题
    3. 🔍 RAG增强：专业知识问答支持
    4. 🎯 最佳匹配：每种查询都得到最适合的处理
    """
    try:
        logger.info("🚀 统一聊天系统启动器...")
        logger.info("📋 系统特性:")
        logger.info("   🚦 智能路由 - 自动选择最佳处理模式")
        logger.info("   💬 直接对话 - 快速响应一般性问题")
        logger.info("   🔍 RAG增强 - 艾尔法尼亚世界专业知识")
        logger.info("   🎯 无缝切换 - 无需手动选择模式")
        logger.info("")
        logger.info("🎮 示例查询:")
        logger.info("   一般对话: '你好'、'今天天气如何'、'讲个笑话'")
        logger.info("   专业知识: '艾尔法尼亚有哪些王国'、'圣剑的能力'、'魔王的弱点'")
        logger.info("")

        # 调用主函数
        main()

    except KeyboardInterrupt:
        logger.info("🛑 用户中断程序")
    except Exception as e:
        logger.error(f"❌ 统一聊天系统启动失败: {e}")
        logger.error("💡 请检查:")
        logger.error("   - DEEPSEEK_API_KEY 环境变量是否设置")
        logger.error("   - ChromaDB 向量数据库是否初始化")
        logger.error("   - SentenceTransformer 模型是否下载")
    finally:
        logger.info("👋 感谢使用统一聊天系统！")


if __name__ == "__main__":
    run_unified_chat_system()
