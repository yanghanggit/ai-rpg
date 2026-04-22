"""
直接调用 DeepSeek API 测试脚本（使用 DeepSeekClient，不依赖 langchain/langgraph）
"""

import asyncio
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from ai_rpg.deepseek import DeepSeekClient
from ai_rpg.models.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    get_buffer_string,
)

_SYSTEM = SystemMessage(content="你是一个有帮助的助手，请用中文回答。")


def test_chat() -> None:
    """测试同步单次请求"""
    print("\n=== 测试 chat() ===")
    client = DeepSeekClient(
        name="test_chat",
        prompt="请简单介绍一下你自己。",
        context=[_SYSTEM],
    )
    client.chat()
    print("📝 回复:")
    print(client.response_content)


async def test_batch_chat() -> None:
    """测试并发批量请求"""
    print("\n=== 测试 batch_chat() ===")
    questions = [
        "1+1等于几？",
        "天空为什么是蓝色的？",
        "请用一句话描述Python语言。",
    ]
    clients = [
        DeepSeekClient(
            name=f"batch_{i}",
            prompt=q,
            context=[_SYSTEM],
        )
        for i, q in enumerate(questions)
    ]

    await DeepSeekClient.batch_chat(clients)

    for client in clients:
        print(f"\n❓ {client.prompt}")
        print(f"💬 {client.response_content}")


def test_get_buffer_string() -> None:
    """测试 get_buffer_string 函数"""
    print("\n=== 测试 get_buffer_string() ===")
    messages = [
        SystemMessage(content="你是一个有帮助的助手。"),
        HumanMessage(content="你好，请介绍一下自己。"),
        AIMessage(content="你好！我是 DeepSeek，一个 AI 助手。"),
        HumanMessage(content="你能做什么？"),
    ]
    result = get_buffer_string(messages)
    print(result)


def test_list_models() -> None:
    """测试列出可用模型"""
    print("\n=== 测试 list_models() ===")
    models = DeepSeekClient.list_models()
    if models:
        print(f"可用模型（共 {len(models)} 个）:")
        for m in models:
            print(f"  - {m}")
    else:
        print("未获取到模型列表")


def test_get_balance() -> None:
    """测试查询账户余额"""
    print("\n=== 测试 get_balance() ===")
    balance = DeepSeekClient.get_balance()
    if balance:
        is_available = balance.get("is_available", False)
        print(f"账户可用: {is_available}")
        for info in balance.get("balance_infos", []):
            currency = info.get("currency", "")
            total = info.get("total_balance", "")
            granted = info.get("granted_balance", "")
            topped_up = info.get("topped_up_balance", "")
            print(f"  货币: {currency}")
            print(f"  总余额:     {total}")
            print(f"  赠送余额:   {granted}")
            print(f"  充值余额:   {topped_up}")
    else:
        print("未获取到余额信息")


def test_cache_tokens() -> None:
    """测试缓存命中 token 统计"""
    print("\n=== 测试 prompt_cache_hit/miss_tokens ===")
    client = DeepSeekClient(
        name="test_cache",
        prompt="请用一句话解释什么是缓存。",
        context=[_SYSTEM],
    )
    client.chat()
    print(f"缓存命中 tokens : {client.prompt_cache_hit_tokens}")
    print(f"缓存未命中 tokens: {client.prompt_cache_miss_tokens}")
    print(f"回复: {client.response_content}")


def main() -> None:
    DeepSeekClient.setup()
    test_get_buffer_string()
    test_list_models()
    test_get_balance()
    test_chat()
    test_cache_tokens()
    asyncio.run(test_batch_chat())


if __name__ == "__main__":
    main()
