from typing import Optional
from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
from pydantic import SecretStr
from langchain_deepseek import ChatDeepSeek


def create_deepseek_llm(temperature: Optional[float] = None) -> ChatDeepSeek:
    """
    创建新的DeepSeek LLM实例

    注意：此实例支持灵活的输出格式控制
    - 默认为自然语言输出
    - 可通过 with_structured_output() 创建结构化输出链
    - 可通过 invoke() 的 config 参数动态控制输出格式

    Returns:
        ChatDeepSeek: 新创建的DeepSeek LLM实例

    Raises:
        ValueError: 当DEEPSEEK_API_KEY环境变量未设置时
    """
    logger.debug("🤖 创建新的DeepSeek LLM实例...")

    # 检查必需的环境变量
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

    # _temperature: float = 0.7  # 默认温度，适合大多数RPG对话场景
    # if option_temperature is not None:
    #     _temperature = float(option_temperature)

    # 设置默认温度
    llm = ChatDeepSeek(
        api_key=SecretStr(deepseek_api_key),
        api_base="https://api.deepseek.com/v1",
        model="deepseek-chat",
        temperature=temperature if temperature is not None else 0.7,
        # 不设置固定的 response_format，保持输出格式的灵活性
    )

    # llm.with_structured_output()

    logger.debug("🤖 DeepSeek LLM实例创建完成")
    return llm
