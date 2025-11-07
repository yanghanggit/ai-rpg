#!/usr/bin/env python3
"""
DeepSeek聊天系统启动脚本

功能：
1. 基于LangGraph构建的DeepSeek聊天机器人
2. 支持连续对话和上下文记忆
3. 提供交互式聊天界面

使用方法：
    python scripts/run_deepseek_chat_client.py

或者在项目根目录下：
    python -m scripts.run_deepseek_chat_client
"""

import os
import sys
import traceback
import asyncio

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

# 导入必要的模块
from typing import List
from langchain.schema import HumanMessage, BaseMessage
from loguru import logger

from ai_rpg.deepseek import (
    create_chat_workflow,
    execute_chat_workflow,
    create_deepseek_llm,
)


async def main() -> None:
    """
    DeepSeek聊天系统主函数

    功能：
    1. 初始化DeepSeek聊天机器人
    2. 提供连续对话能力
    3. 支持上下文记忆
    4. 优雅的错误处理
    """
    logger.info("🤖 启动DeepSeek聊天系统...")

    try:

        # 聊天历史（消息列表）
        context_messages: List[BaseMessage] = []
        llm = create_deepseek_llm()

        logger.success("🤖 DeepSeek聊天系统初始化完成，开始对话...")
        logger.info("💡 提示：您可以与DeepSeek AI进行自由对话")
        logger.info("💡 输入 /quit、/exit 或 /q 退出程序")

        while True:
            try:
                print("\n" + "=" * 60)
                user_input = input("User: ")

                if user_input.lower() in ["/quit", "/exit", "/q"]:
                    print("Goodbye!")
                    break

                # 用户输入
                user_message = HumanMessage(content=user_input)

                # 获取回复
                chat_response = await execute_chat_workflow(
                    work_flow=create_chat_workflow(),
                    context=context_messages,
                    request=user_message,
                    llm=llm,
                )

                # 测试用：记录上下文。
                context_messages.append(user_message)
                context_messages.extend(chat_response)

                # 显示最新的AI回复
                if chat_response:
                    latest_response = chat_response[-1]
                    print(f"\nDeepSeek: {latest_response.content}")

                logger.debug("*" * 50)
                for message in context_messages:
                    if isinstance(message, HumanMessage):
                        logger.info(f"User: {message.content}")
                    else:
                        logger.success(f"Deepseek: {message.content}")

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
    asyncio.run(main())
