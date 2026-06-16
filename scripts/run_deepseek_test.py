"""
直接调用 DeepSeek API 测试脚本（使用 DeepSeekClient，不依赖 langchain/langgraph）
"""

import asyncio
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from ai_rpg.deepseek import (
    DeepSeekClient,
    MODEL_FLASH,
    MODEL_PRO,
    ToolDefinition,
    ToolFunction,
)
from ai_rpg.models.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    get_buffer_string,
)

_SYSTEM = SystemMessage(content="你是一个有帮助的助手，请用中文回答。")


async def test_chat() -> None:
    """测试异步单次请求"""
    print("\n=== 测试 chat() ===")
    client = DeepSeekClient(
        name="test_chat",
        prompt="请简单介绍一下你自己。",
        context=[_SYSTEM],
    )
    await client.chat()
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

    await DeepSeekClient.close_async_client()


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


async def test_cache_tokens() -> None:
    """测试缓存命中 token 统计"""
    print("\n=== 测试 prompt_cache_hit/miss_tokens ===")
    client = DeepSeekClient(
        name="test_cache",
        prompt="请用一句话解释什么是缓存。",
        context=[_SYSTEM],
    )
    await client.chat()
    print(f"缓存命中 tokens : {client.prompt_cache_hit_tokens}")
    print(f"缓存未命中 tokens: {client.prompt_cache_miss_tokens}")
    print(f"回复: {client.response_content}")


async def test_model_matrix() -> None:
    """2x2 矩阵测试：flash/pro × thinking=False/True"""
    print("\n=== 测试 2x2 模型矩阵（flash/pro × thinking off/on）===")
    _PROMPT = "请用一句话解释什么是递归。"
    cases = [
        (MODEL_FLASH, False),
        (MODEL_FLASH, True),
        (MODEL_PRO, False),
        (MODEL_PRO, True),
    ]
    clients = [
        DeepSeekClient(
            name=f"{model}__thinking={thinking}",
            prompt=_PROMPT,
            context=[_SYSTEM],
            model=model,
            thinking=thinking,
        )
        for model, thinking in cases
    ]

    await DeepSeekClient.batch_chat(clients)

    for client in clients:
        label = client.name
        print(f"\n[{label}]")
        print(f"  回复: {client.response_content}")
        if client.response_reasoning_content:
            preview = client.response_reasoning_content[:120].replace("\n", " ")
            print(f"  思考: {preview}...")

    await DeepSeekClient.close_async_client()


# 工具定义：模拟一个天气查询工具
_WEATHER_TOOL = ToolDefinition(
    function=ToolFunction(
        name="get_current_weather",
        description="获取指定城市的当前天气信息",
        parameters={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，例如 '北京'、'上海'",
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "温度单位",
                },
            },
            "required": ["city"],
        },
    )
)


def _mock_get_weather(city: str, unit: str = "celsius") -> str:
    """模拟天气查询结果（实际使用时应调用真实天气 API）"""
    _data = {
        "北京": ("25°C", "晴天"),
        "上海": ("28°C", "多云"),
        "广州": ("32°C", "雷阵雨"),
    }
    temp, cond = _data.get(city, ("20°C", "未知"))
    if unit == "fahrenheit":
        temp = temp.replace("°C", "°F")
    return f"{city}当前天气：{temp}，{cond}"


async def test_tool_call_single() -> None:
    """测试工具调用第一轮：LLM 返回 tool_calls，尚未执行工具"""
    print("\n=== 测试 tool calling 第一转（LLM 返回 tool_calls）===")
    client = DeepSeekClient(
        name="test_tool_single",
        prompt="北京现在天气怎么样？",
        context=[_SYSTEM],
        tools=[_WEATHER_TOOL],
    )
    await client.chat()

    print(f"finish_reason : {client.finish_reason}")
    print(f"tool_calls 数量: {len(client.tool_calls)}")
    for tc in client.tool_calls:
        import json

        args = json.loads(tc.function.arguments)
        print(f"  工具名称 : {tc.function.name}")
        print(f"  调用参数 : {args}")
        print(f"  调用 ID   : {tc.id}")

    assert (
        client.finish_reason == "tool_calls"
    ), f"预期 finish_reason='tool_calls'，实际得到='{client.finish_reason}'"
    assert len(client.tool_calls) > 0, "预期至少一个 tool call"
    print("✅ 第一转工具调用验证通过")


async def test_tool_call_full_round() -> None:
    """测试工具调用完整两转：LLM 调用工具 → Python 执行 → 回传结果 → LLM 给出最终回复"""
    print("\n=== 测试 tool calling 完整两转（agentic loop）===")
    import json

    user_question = "北京和上海分别是什么天气？"

    # 转 1：LLM 返回 tool_calls
    first = DeepSeekClient(
        name="tool_round1",
        prompt=user_question,
        context=[_SYSTEM],
        tools=[_WEATHER_TOOL],
    )
    await first.chat()
    print(
        f"[转 1] finish_reason={first.finish_reason}, tool_calls={len(first.tool_calls)}"
    )
    assert (
        first.finish_reason == "tool_calls" and first.tool_calls
    ), "转 1 预期 tool_calls"

    # 执行工具，构建回传上下文
    assert first.response_ai_message is not None
    history = list(first._context) + [
        HumanMessage(content=user_question),
        first.response_ai_message,
    ]
    for tc in first.tool_calls:
        args = json.loads(tc.function.arguments)
        result = _mock_get_weather(**args)
        print(f"  工具执行: {tc.function.name}({args}) → {result}")
        history.append(ToolMessage(content=result, tool_call_id=tc.id))

    # 转 2：LLM 利用工具结果给出自然语言回复
    second = DeepSeekClient(
        name="tool_round2",
        prompt="",  # continuation 模式
        context=history,
        tools=[_WEATHER_TOOL],
        tool_choice="none",  # 强制回答，不再调用工具
    )
    await second.chat()
    print(f"[转 2] finish_reason={second.finish_reason}")
    print(f"最终回复: {second.response_content}")
    assert (
        second.finish_reason == "stop"
    ), f"转 2 预期 finish_reason='stop'，得到='{second.finish_reason}'"
    assert second.response_content, "转 2 回复不应为空"
    print("✅ 完整两转工具调用验证通过")


def main() -> None:
    DeepSeekClient.setup()
    test_get_buffer_string()
    test_list_models()
    test_get_balance()
    asyncio.run(test_chat())
    asyncio.run(test_cache_tokens())
    asyncio.run(test_batch_chat())
    asyncio.run(test_model_matrix())
    asyncio.run(test_tool_call_single())
    asyncio.run(test_tool_call_full_round())


if __name__ == "__main__":
    main()
