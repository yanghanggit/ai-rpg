#!/usr/bin/env python3
"""
Replicate 对话工具
一个简单易用的对话脚本，支持多种LLM模型进行对话
"""

import argparse
import os
import sys
import time
from typing import Dict, Final, List

import replicate
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 内置对话模型配置
CHAT_MODELS: Dict[str, Dict[str, str]] = {
    "gpt-4o-mini": {
        "version": "openai/gpt-4o-mini",
        "cost_estimate": "$0.15/1M input + $0.6/1M output tokens",
        "description": "OpenAI 低成本高效对话模型，推荐日常使用",
    },
    "gpt-4o": {
        "version": "openai/gpt-4o",
        "cost_estimate": "$2.5/1M input + $10/1M output tokens",
        "description": "OpenAI 高智能多模态对话模型",
    },
    "claude-3.5-sonnet": {
        "version": "anthropic/claude-3.5-sonnet",
        "cost_estimate": "中等成本，高质量对话",
        "description": "Anthropic 高智能对话模型，擅长分析和推理",
    },
    "llama-3.1-405b": {
        "version": "meta/meta-llama-3.1-405b-instruct",
        "cost_estimate": "开源大模型，成本较高",
        "description": "Meta 开源旗舰对话模型",
    },
    "llama-3-70b": {
        "version": "meta/meta-llama-3-70b-instruct",
        "cost_estimate": "开源模型，平衡性能和成本",
        "description": "Meta 开源对话模型，性价比高",
    },
}

# 全局变量
API_TOKEN: str = os.getenv("REPLICATE_API_TOKEN") or ""
TEST_URL: Final[str] = "https://api.replicate.com/v1/models"
DEFAULT_MODEL: Final[str] = "gpt-4o-mini"


def test_connection() -> bool:
    """测试连接是否正常"""
    headers = {"Authorization": f"Token {API_TOKEN}"}

    try:
        print("🔄 测试 Replicate API 连接...")
        response = requests.get(TEST_URL, headers=headers, timeout=10)

        if response.status_code == 200:
            print("✅ 连接成功! Replicate API 可正常访问")
            return True
        else:
            print(f"❌ 连接失败，状态码: {response.status_code}")
            if response.status_code == 401:
                print("💡 API Token 可能无效或已过期")
            return False

    except Exception as e:
        print(f"❌ 连接错误: {e}")
        print("💡 请检查:")
        print("   1. 网络连接是否正常")
        print("   2. API Token 是否有效")
        return False


def chat_single(
    prompt: str,
    model_name: str = DEFAULT_MODEL,
    system_prompt: str = "You are a helpful assistant.",
    max_tokens: int = 1000,
    temperature: float = 0.7,
    stream: bool = False,
) -> str:
    """
    单次对话

    Args:
        prompt: 用户输入的消息
        model_name: 模型名称
        system_prompt: 系统提示词
        max_tokens: 最大token数
        temperature: 温度参数（0-2）
        stream: 是否流式输出

    Returns:
        模型回复
    """
    if model_name not in CHAT_MODELS:
        raise ValueError(
            f"不支持的模型: {model_name}. 可用模型: {list(CHAT_MODELS.keys())}"
        )

    model_info = CHAT_MODELS[model_name]
    model_version = model_info["version"]
    cost_estimate = model_info["cost_estimate"]

    print(f"\n🤖 使用模型: {model_name}")
    print(f"💰 预估成本: {cost_estimate}")
    print(f"📝 用户输入: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    print("🔄 思考中...")

    start_time = time.time()

    try:
        # 构建输入参数
        input_params = {
            "prompt": prompt,
            "system_prompt": system_prompt,
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
        }

        if stream:
            # 流式输出
            print("\n🎯 AI 回复:")
            print("-" * 50)

            iterator = replicate.run(model_version, input=input_params)
            full_response = ""

            for text in iterator:
                print(text, end="", flush=True)
                full_response += text

            print()  # 换行
            print("-" * 50)

            elapsed_time = time.time() - start_time
            print(f"⏱️  完成时间: {elapsed_time:.2f}秒")

            return full_response
        else:
            # 一次性输出
            output = replicate.run(model_version, input=input_params)

            response = ""
            if isinstance(output, list):
                response = "".join(str(item) for item in output)
            else:
                response = str(output)

            elapsed_time = time.time() - start_time
            print(f"\n🎯 AI 回复:")
            print("-" * 50)
            print(response)
            print("-" * 50)
            print(f"⏱️  完成时间: {elapsed_time:.2f}秒")

            return response

    except Exception as e:
        print(f"❌ 对话失败: {e}")
        raise


def chat_interactive(
    model_name: str = DEFAULT_MODEL,
    system_prompt: str = "You are a helpful assistant.",
    stream: bool = True,
) -> None:
    """
    交互式对话模式

    Args:
        model_name: 模型名称
        system_prompt: 系统提示词
        stream: 是否流式输出
    """
    print("=" * 60)
    print("🎮 Replicate 交互式对话")
    print("=" * 60)
    print(f"🤖 当前模型: {model_name}")
    print(f"📋 模型描述: {CHAT_MODELS[model_name]['description']}")
    print(f"💰 成本估算: {CHAT_MODELS[model_name]['cost_estimate']}")
    print("\n💡 使用说明:")
    print("   - 直接输入消息开始对话")
    print("   - 输入 'quit' 或 'exit' 退出")
    print("   - 输入 'clear' 清空对话历史")
    print("   - 输入 'help' 查看帮助")
    print("=" * 60)

    conversation_history: List[str] = []

    while True:
        try:
            # 获取用户输入
            user_input = input("\n👤 你: ").strip()

            if not user_input:
                continue

            # 处理特殊命令
            if user_input.lower() in ["quit", "exit"]:
                print("👋 再见!")
                break
            elif user_input.lower() == "clear":
                conversation_history.clear()
                print("🧹 对话历史已清空")
                continue
            elif user_input.lower() == "help":
                print("\n📖 可用命令:")
                print("   - quit/exit: 退出对话")
                print("   - clear: 清空对话历史")
                print("   - help: 显示帮助")
                continue

            # 添加到对话历史
            conversation_history.append(f"用户: {user_input}")

            # 构建完整的对话上下文
            if len(conversation_history) > 1:
                context = "\n".join(conversation_history[-10:])  # 保留最近10轮对话
                full_prompt = f"对话历史:\n{context}\n\n请回复最新的用户消息。"
            else:
                full_prompt = user_input

            # 发送给AI
            response = chat_single(
                prompt=full_prompt,
                model_name=model_name,
                system_prompt=system_prompt,
                stream=stream,
            )

            # 添加AI回复到历史
            conversation_history.append(f"AI: {response}")

        except KeyboardInterrupt:
            print("\n\n👋 用户中断，再见!")
            break
        except Exception as e:
            print(f"\n❌ 对话出错: {e}")


def run_demo() -> None:
    """运行演示示例"""
    print("=" * 60)
    print("🎮 Replicate 对话演示")
    print("=" * 60)

    # 1. 测试连接
    if not test_connection():
        print("❌ 连接测试失败，请检查网络设置")
        return

    # 2. 查看可用模型
    print("\n📋 可用对话模型:")
    for name, info in CHAT_MODELS.items():
        cost = info["cost_estimate"]
        description = info["description"]
        print(f"  - {name}:")
        print(f"    💰 {cost}")
        print(f"    📝 {description}")

    # 3. 测试对话
    print("\n🤖 测试对话功能...")

    try:
        test_prompt = "你好！请简单介绍一下你自己。"

        response = chat_single(
            prompt=test_prompt, model_name=DEFAULT_MODEL, stream=False
        )

        print(f"\n🎉 演示完成!")
        print("💡 您可以使用 --interactive 模式进行连续对话")

    except Exception as e:
        print(f"❌ 演示失败: {e}")


def main() -> None:
    """主函数 - 命令行接口"""
    if not API_TOKEN:
        print("❌ 错误: API Token 未配置")
        print("💡 请检查:")
        print("   1. 环境变量 REPLICATE_API_TOKEN 是否设置")
        print("   2. .env 文件是否存在且包含正确的 API Token")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Replicate 对话工具")
    parser.add_argument("prompt", nargs="?", help="对话内容")
    parser.add_argument(
        "--model",
        "-m",
        default=DEFAULT_MODEL,
        choices=list(CHAT_MODELS.keys()),
        help=f"使用的模型 (默认: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--system", "-s", default="You are a helpful assistant.", help="系统提示词"
    )
    parser.add_argument(
        "--max-tokens", "-t", type=int, default=1000, help="最大token数 (默认: 1000)"
    )
    parser.add_argument(
        "--temperature", type=float, default=0.7, help="温度参数 0-2 (默认: 0.7)"
    )
    parser.add_argument("--no-stream", action="store_true", help="禁用流式输出")
    parser.add_argument(
        "--interactive", "-i", action="store_true", help="进入交互式对话模式"
    )
    parser.add_argument("--list-models", action="store_true", help="列出可用模型")
    parser.add_argument("--demo", action="store_true", help="运行演示")
    parser.add_argument("--test", action="store_true", help="测试连接")

    args = parser.parse_args()

    try:
        print("✅ Replicate 客户端初始化完成")

        # 运行演示
        if args.demo:
            run_demo()
            return

        # 测试连接
        if args.test:
            test_connection()
            return

        # 列出模型
        if args.list_models:
            print("🤖 可用对话模型:")
            for name, info in CHAT_MODELS.items():
                cost = info["cost_estimate"]
                description = info["description"]
                print(f"  - {name}:")
                print(f"    💰 {cost}")
                print(f"    📝 {description}")
            return

        # 交互式模式
        if args.interactive:
            chat_interactive(
                model_name=args.model,
                system_prompt=args.system,
                stream=not args.no_stream,
            )
            return

        # 如果没有提供prompt，显示帮助
        if not args.prompt:
            print("🤖 Replicate 对话工具")
            print("\n快速开始:")
            print("  python replicate_chat.py --demo              # 运行演示")
            print("  python replicate_chat.py --test              # 测试连接")
            print("  python replicate_chat.py --list-models       # 查看可用模型")
            print("  python replicate_chat.py --interactive       # 交互式对话")
            print('  python replicate_chat.py "你好，介绍一下自己"   # 单次对话')
            print("\n模型选择:")
            for name, info in CHAT_MODELS.items():
                print(f"  --model {name:<15} # {info['description']}")
            print("\n详细帮助:")
            print("  python replicate_chat.py -h")
            return

        # 单次对话
        response = chat_single(
            prompt=args.prompt,
            model_name=args.model,
            system_prompt=args.system,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            stream=not args.no_stream,
        )

        print(f"\n🎉 对话完成!")

    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
