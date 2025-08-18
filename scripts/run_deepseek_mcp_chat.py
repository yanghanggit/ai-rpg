#!/usr/bin/env python3
"""
DeepSeek + MCP 聊天系统启动脚本

功能：
1. 基于LangGraph构建的DeepSeek + MCP聊天机器人
2. 支持 Model Context Protocol (MCP) 工具调用
3. 支持连续对话和上下文记忆
4. 提供交互式聊天界面，包含工具功能演示

特性：
- 完全独立的MCP实现，不影响原有的DeepSeek Chat功能
- 内置示例工具：时间查询、计算器、文本处理
- 智能工具调用检测和执行
- 工具执行结果实时显示

使用方法：
    python scripts/run_deepseek_mcp_chat.py

或者在项目根目录下：
    python -m scripts.run_deepseek_mcp_chat
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

from multi_agents_game.chat_services.chat_deepseek_mcp_graph import (
    McpState,
    create_compiled_mcp_stage_graph,
    stream_mcp_graph_updates,
    create_sample_mcp_tools,
)


def print_welcome_message():
    """打印欢迎信息和功能说明"""
    print("\n" + "🚀" * 60)
    print("🤖 DeepSeek + MCP 聊天系统")
    print("📚 Model Context Protocol 增强版本")
    print("🚀" * 60)
    print("\n✨ 功能特性：")
    print("  • 智能对话：基于 DeepSeek AI 的强大对话能力")
    print("  • 工具调用：集成 MCP 工具，支持实用功能")
    print("  • 上下文记忆：维护完整的对话历史")
    print("  • 实时反馈：工具执行结果即时显示")
    
    print("\n🛠️ 内置工具：")
    print("  • 时间查询：获取当前系统时间")
    print("  • 计算器：执行数学计算")
    print("  • 文本处理：大小写转换、字符统计等")
    
    print("\n💡 使用提示：")
    print("  • 你可以直接对话，AI会智能判断是否需要使用工具")
    print("  • 尝试说：'现在几点了？'、'计算 25 * 4'、'把HELLO转为小写'")
    print("  • 输入 /tools 查看可用工具详情")
    print("  • 输入 /quit、/exit 或 /q 退出程序")
    print("\n" + "🎯" * 60 + "\n")


def print_available_tools():
    """打印可用工具的详细信息"""
    tools = create_sample_mcp_tools()
    print("\n🛠️ 可用工具详情：")
    print("-" * 50)
    
    for i, tool in enumerate(tools, 1):
        print(f"{i}. {tool['name']}")
        print(f"   描述：{tool['description']}")
        if tool['parameters']:
            print("   参数：")
            for param, details in tool['parameters'].items():
                print(f"     - {param}: {details.get('description', 'N/A')}")
        print()


def main() -> None:
    """
    DeepSeek + MCP 聊天系统主函数

    功能：
    1. 初始化 DeepSeek + MCP 聊天机器人
    2. 提供 MCP 工具调用能力
    3. 支持连续对话和上下文记忆
    4. 优雅的错误处理和用户体验
    """
    logger.info("🤖 启动 DeepSeek + MCP 聊天系统...")

    try:
        # 打印欢迎信息
        print_welcome_message()
        
        # 初始化 MCP 聊天历史状态
        chat_history_state: McpState = {
            "messages": [],
            "tools_available": create_sample_mcp_tools(),
            "tool_outputs": [],
            "enable_tools": True
        }

        # 生成 MCP 增强的聊天机器人状态图
        compiled_mcp_stage_graph = create_compiled_mcp_stage_graph(
            "deepseek_mcp_chatbot_node", 
            temperature=0.7,
            enable_tools=True
        )

        logger.success("🤖 DeepSeek + MCP 聊天系统初始化完成，开始对话...")

        while True:
            try:
                print("\n" + "=" * 60)
                user_input = input("User: ").strip()

                # 处理特殊命令
                if user_input.lower() in ["/quit", "/exit", "/q"]:
                    print("\n👋 感谢使用 DeepSeek + MCP 聊天系统！再见！")
                    break
                elif user_input.lower() == "/tools":
                    print_available_tools()
                    continue
                elif user_input.lower() == "/help":
                    print_welcome_message()
                    continue
                elif user_input == "":
                    print("💡 请输入您的问题，或输入 /help 查看帮助")
                    continue

                # 用户输入状态
                user_input_state: McpState = {
                    "messages": [HumanMessage(content=user_input)],
                    "tools_available": chat_history_state["tools_available"],
                    "tool_outputs": [],
                    "enable_tools": True
                }

                # 获取 AI 回复（包含可能的工具调用）
                logger.info(f"处理用户输入: {user_input}")
                update_messages = stream_mcp_graph_updates(
                    state_compiled_graph=compiled_mcp_stage_graph,
                    chat_history_state=chat_history_state,
                    user_input_state=user_input_state,
                )

                # 更新聊天历史（包含用户输入和AI回复）
                chat_history_state["messages"].extend(user_input_state["messages"])
                chat_history_state["messages"].extend(update_messages)

                # 显示最新的AI回复
                if update_messages:
                    latest_response = update_messages[-1]
                    print(f"\n🤖 DeepSeek: {latest_response.content}")
                else:
                    print("\n❌ 抱歉，没有收到回复。")

                # 调试信息：显示对话历史（仅在调试模式下）
                if logger.level.name == "DEBUG":
                    logger.debug("=" * 50)
                    for message in chat_history_state["messages"][-4:]:  # 只显示最近4条消息
                        if isinstance(message, HumanMessage):
                            logger.debug(f"User: {message.content}")
                        else:
                            logger.debug(f"DeepSeek: {message.content[:100]}...")

            except KeyboardInterrupt:
                logger.info("🛑 [MAIN] 用户中断程序")
                print("\n\n👋 程序已中断。再见！")
                break
            except Exception as e:
                logger.error(
                    f"❌ 处理用户输入时发生错误: {e}\n"
                    f"Traceback: {traceback.format_exc()}"
                )
                print("\n❌ 抱歉，处理您的请求时发生错误，请重试。")

    except Exception as e:
        logger.error(f"❌ [MAIN] 系统启动失败: {e}")
        print(f"\n❌ 系统启动失败：{e}")
        print("请检查以下项目：")
        print("  1. DEEPSEEK_API_KEY 环境变量是否设置")
        print("  2. 网络连接是否正常")
        print("  3. 依赖包是否正确安装")

    finally:
        logger.info("🔒 [MAIN] 清理系统资源...")


if __name__ == "__main__":
    main()
