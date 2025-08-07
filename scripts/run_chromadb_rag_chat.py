#!/usr/bin/env python3
"""
ChromaDB增强版RAG聊天系统启动脚本

功能：
1. 初始化ChromaDB向量数据库
2. 加载SentenceTransformer模型
3. 支持语义搜索和关键词搜索回退
4. 提供交互式聊天界面

使用方法：
    python scripts/run_chromadb_rag_chat.py

或者在项目根目录下：
    python -m scripts.run_chromadb_rag_chat
"""

import sys
import os

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

# 导入必要的模块
from loguru import logger
from langchain.schema import HumanMessage
from multi_agents_game.chat_services.chat_deepseek_rag_graph import (
    State,
    create_rag_compiled_graph,
    stream_rag_graph_updates,
)


def main() -> None:
    """
    ChromaDB增强版RAG聊天系统主函数

    功能改进：
    1. 初始化ChromaDB向量数据库
    2. 加载SentenceTransformer模型
    3. 支持语义搜索和关键词搜索回退
    4. 提供丰富的使用提示和错误处理
    """
    logger.info("🎯 启动ChromaDB增强版RAG聊天系统...")

    try:

        # 步骤2: 创建RAG状态图
        rag_compiled_graph = create_rag_compiled_graph()

        # 步骤3: 初始化聊天历史
        chat_history_state: State = {"messages": []}

        logger.success("🎯 RAG系统初始化完成，开始对话...")
        logger.info("💡 提示：您可以询问关于艾尔法尼亚世界的问题，例如：")
        logger.info("   - 艾尔法尼亚大陆有哪些王国？")
        logger.info("   - 圣剑有什么特殊能力？")
        logger.info("   - 魔王阿巴顿的弱点是什么？")
        logger.info("   - 有哪些种族生活在这片大陆？")
        logger.info("   - 著名的遗迹有哪些？")
        logger.info("   - 冒险者公会是如何运作的？")
        logger.info("💡 输入 /quit、/exit 或 /q 退出程序")

        # 步骤4: 开始交互循环
        while True:
            try:
                print("\n" + "=" * 60)
                user_input = input("User: ")

                if user_input.lower() in ["/quit", "/exit", "/q"]:
                    print("Goodbye!")
                    break

                # 用户输入
                user_input_state: State = {
                    "messages": [HumanMessage(content=user_input)]
                }

                # 执行RAG流程
                update_messages = stream_rag_graph_updates(
                    rag_compiled_graph=rag_compiled_graph,
                    chat_history_state=chat_history_state,
                    user_input_state=user_input_state,
                )

                # 更新聊天历史
                chat_history_state["messages"].extend(user_input_state["messages"])
                chat_history_state["messages"].extend(update_messages)

                # 显示最新的AI回复
                if update_messages:
                    latest_response = update_messages[-1]
                    print(f"\nDeepSeek: {latest_response.content}")
                    logger.success(f"✅ RAG回答: {latest_response.content}")

                logger.debug("=" * 60)

            except KeyboardInterrupt:
                logger.info("🛑 [MAIN] 用户中断程序")
                break
            except Exception as e:
                logger.error(
                    f"❌ RAG流程处理错误: {e}\n" f"Traceback: {sys.exc_info()}"
                )
                print("抱歉，处理您的请求时发生错误，请重试。")

    except Exception as e:
        logger.error(f"❌ [MAIN] 系统启动失败: {e}")
        print("系统启动失败，请检查环境配置。")

    finally:
        logger.info("🔒 [MAIN] 清理系统资源...")


if __name__ == "__main__":
    main()
