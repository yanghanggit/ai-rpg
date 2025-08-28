from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
from pydantic import SecretStr
from langchain_deepseek import ChatDeepSeek


def create_deepseek_llm() -> ChatDeepSeek:
    """
    创建新的DeepSeek LLM实例

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

    llm = ChatDeepSeek(
        api_key=SecretStr(deepseek_api_key),
        model="deepseek-chat",
        temperature=0.7,
    )

    logger.debug("🤖 DeepSeek LLM实例创建完成")
    return llm
