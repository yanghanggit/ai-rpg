#!/usr/bin/env python3
"""
Azure OpenAI GPT-4o聊天系统启动脚本

功能：
1. 基于LangGraph构建的Azure OpenAI GPT-4o聊天机器人
2. 支持连续对话和上下文记忆
3. 提供交互式聊天界面

使用方法：
    python scripts/run_azure_openai_chat.py

或者在项目根目录下：
    python -m scripts.run_azure_openai_chat
"""

import os
import sys
import traceback

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

# 导入必要的模块
from langchain.schema import HumanMessage
from loguru import logger

from multi_agents_game.chat_services.chat_azure_openai_gpt_4o_graph import (
    State,
    create_compiled_stage_graph,
    stream_graph_updates,
)


def main() -> None:
    """
    Azure OpenAI GPT-4o聊天系统主函数

    功能：
    1. 初始化Azure OpenAI GPT-4o聊天机器人
    2. 提供连续对话能力
    3. 支持上下文记忆
    4. 优雅的错误处理
    """
    logger.info("🤖 启动Azure OpenAI GPT-4o聊天系统...")

    try:
        # 聊天历史
        chat_history_state: State = {"messages": []}

        # 生成聊天机器人状态图
        compiled_stage_graph = create_compiled_stage_graph(
            "azure_chat_openai_chatbot_node"
        )

        logger.success("🤖 Azure OpenAI GPT-4o聊天系统初始化完成，开始对话...")
        logger.info("💡 提示：您可以与Azure OpenAI GPT-4o进行自由对话")
        logger.info("💡 输入 /quit、/exit 或 /q 退出程序")

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

                # 获取回复
                update_messages = stream_graph_updates(
                    state_compiled_graph=compiled_stage_graph,
                    chat_history_state=chat_history_state,
                    user_input_state=user_input_state,
                )

                # 测试用：记录上下文。
                chat_history_state["messages"].extend(user_input_state["messages"])
                chat_history_state["messages"].extend(update_messages)

                # 显示最新的AI回复
                if update_messages:
                    latest_response = update_messages[-1]
                    print(f"\nAzure-OpenAI-GPT4o: {latest_response.content}")

                logger.debug("*" * 50)
                for message in chat_history_state["messages"]:
                    if isinstance(message, HumanMessage):
                        logger.info(f"User: {message.content}")
                    else:
                        logger.success(f"Azure-OpenAI-GPT4o: {message.content}")

            except KeyboardInterrupt:
                logger.info("🛑 [MAIN] 用户中断程序")
                break
            except Exception as e:
                logger.error(
                    f"❌ Error in processing user input = {e}\n"
                    f"Traceback: {traceback.format_exc()}"
                )
                print("抱歉，处理您的请求时发生错误，请重试。")

    except Exception as e:
        logger.error(f"❌ [MAIN] 系统启动失败: {e}")
        print("系统启动失败，请检查环境配置。")

    finally:
        logger.info("🔒 [MAIN] 清理系统资源...")


if __name__ == "__main__":
    main()
