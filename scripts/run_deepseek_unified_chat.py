#!/usr/bin/env python3
"""
统一聊天系统启动脚
). 智能路由：自动检测查询类型并选择最佳处理模式
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

import traceback
from typing import Dict, List

from langchain.schema import HumanMessage
from langchain_core.messages import BaseMessage
from loguru import logger

from multi_agents_game.deepseek.unified_chat_graph import (
    create_unified_chat_graph,
    stream_unified_graph_updates,
)
from multi_agents_game.rag.routing import (
    KeywordRouteStrategy,
    SemanticRouteStrategy,
    RouteDecisionManager,
    FallbackRouteStrategy,
    RouteConfigBuilder,
)
from multi_agents_game.demo.campaign_setting import (
    FANTASY_WORLD_RPG_TEST_ROUTE_KEYWORDS,
    FANTASY_WORLD_RPG_TEST_RAG_TOPICS,
)


# =============================================================================
# 业务耦合的硬编码配置函数（移入脚本）
# =============================================================================


def create_alphania_keyword_strategy() -> KeywordRouteStrategy:
    """创建艾尔法尼亚世界专用的关键词策略"""

    # 使用测试配置中的关键词列表
    alphania_keywords = FANTASY_WORLD_RPG_TEST_ROUTE_KEYWORDS

    config = {
        "keywords": alphania_keywords,
        "threshold": 0.1,  # 较低阈值，只要匹配到关键词就启用RAG
        "case_sensitive": False,
    }

    return KeywordRouteStrategy(config)


def create_game_semantic_strategy() -> SemanticRouteStrategy:
    """创建游戏专用的语义路由策略"""

    config = {
        "similarity_threshold": 0.5,  # 中等相似度阈值
        "use_multilingual": True,  # 使用多语言模型支持中文
        "rag_topics": FANTASY_WORLD_RPG_TEST_RAG_TOPICS,
    }

    return SemanticRouteStrategy(config)


def create_default_route_manager() -> RouteDecisionManager:
    """创建默认的路由决策管理器"""
    # 创建策略实例
    keyword_strategy = create_alphania_keyword_strategy()
    semantic_strategy = create_game_semantic_strategy()

    # 使用构建器创建管理器
    builder = RouteConfigBuilder()
    builder.add_strategy(keyword_strategy, 0.4)
    builder.add_strategy(semantic_strategy, 0.6)
    builder.set_fallback(FallbackRouteStrategy(default_to_rag=False))

    return builder.build()


# =============================================================================
# 主要功能函数
# =============================================================================


def main() -> None:
    """
    统一聊天系统主函数

    功能：
    - 创建统一聊天图
    - 提供交互式命令行界面
    - 支持直接对话和RAG增强两种模式的智能切换
    """
    logger.info("🎯 启动统一聊天系统...")

    try:
        # 创建统一聊天图
        unified_graph = create_unified_chat_graph()

        # 创建路由管理器实例
        route_manager = create_default_route_manager()

        # 初始化聊天历史
        chat_history_state: Dict[str, List[BaseMessage]] = {"messages": []}

        logger.success("🎯 统一聊天系统初始化完成")
        logger.info("💡 提示：系统会自动检测您的查询类型并选择最佳处理模式")
        logger.info("   - 涉及艾尔法尼亚世界的问题将使用RAG增强模式")
        logger.info("   - 一般性对话将使用直接对话模式")
        logger.info("💡 输入 /quit、/exit 或 /q 退出程序")

        # 开始交互循环
        while True:
            try:
                print("\n" + "=" * 60)
                user_input = input("User: ")

                if user_input.lower() in ["/quit", "/exit", "/q"]:
                    print("Goodbye!")
                    break

                # 用户输入状态
                user_input_state: Dict[str, List[BaseMessage]] = {
                    "messages": [HumanMessage(content=user_input)]
                }

                # 执行统一图流程
                update_messages = stream_unified_graph_updates(
                    unified_compiled_graph=unified_graph,
                    chat_history_state=chat_history_state,
                    user_input_state=user_input_state,
                    route_manager=route_manager,  # 传入路由管理器
                )

                # 更新聊天历史
                chat_history_state["messages"].extend(user_input_state["messages"])
                chat_history_state["messages"].extend(update_messages)

                # 显示最新的AI回复
                if update_messages:
                    latest_response = update_messages[-1]
                    print(f"\nDeepSeek: {latest_response.content}")
                    logger.success(f"✅ 系统回答: {latest_response.content}")

                logger.debug("=" * 60)

            except KeyboardInterrupt:
                logger.info("🛑 [MAIN] 用户中断程序")
                break
            except Exception as e:
                logger.error(f"❌ 统一聊天流程处理错误: {e}\n{traceback.format_exc()}")
                print("抱歉，处理您的请求时发生错误，请重试。")

    except Exception as e:
        logger.error(f"❌ [MAIN] 统一聊天系统启动失败: {e}")
        print("系统启动失败，请检查环境配置。")

    finally:
        logger.info("🔒 [MAIN] 清理系统资源...")


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
