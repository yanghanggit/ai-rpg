from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
from typing import Optional
from langchain_openai import AzureChatOpenAI
from pydantic import SecretStr


# 全局Azure OpenAI GPT实例（懒加载单例）
_global_azure_openai_gpt_llm: Optional[AzureChatOpenAI] = None


def get_azure_openai_gpt_llm() -> AzureChatOpenAI:
    """
    获取全局Azure OpenAI GPT实例（懒加载单例模式）

    Returns:
        AzureChatOpenAI: 配置好的Azure OpenAI GPT实例

    Raises:
        ValueError: 当AZURE_OPENAI_API_KEY环境变量未设置时
    """
    global _global_azure_openai_gpt_llm

    if _global_azure_openai_gpt_llm is None:
        logger.info("🤖 初始化全局Azure OpenAI GPT实例...")

        # 检查必需的环境变量
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")

        if not azure_endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is not set")

        if not azure_api_key:
            raise ValueError("AZURE_OPENAI_API_KEY environment variable is not set")

        _global_azure_openai_gpt_llm = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=SecretStr(azure_api_key),
            azure_deployment="gpt-4o",
            api_version="2024-02-01",
            temperature=0.7,
        )

        logger.success("🤖 全局DeepSeek LLM实例创建完成")

    return _global_azure_openai_gpt_llm
