from typing import Optional
from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
from langchain_openai import AzureChatOpenAI
from pydantic import SecretStr


def create_azure_openai_gpt_llm(temperature: Optional[float] = None) -> AzureChatOpenAI:
    """
    创建新的Azure OpenAI GPT实例

    Returns:
        AzureChatOpenAI: 新创建的Azure OpenAI GPT实例

    Raises:
        ValueError: 当AZURE_OPENAI_API_KEY环境变量未设置时
    """
    logger.debug("🤖 创建新的Azure OpenAI GPT实例...")

    # 检查必需的环境变量
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")

    if not azure_endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is not set")

    if not azure_api_key:
        raise ValueError("AZURE_OPENAI_API_KEY environment variable is not set")

    llm = AzureChatOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=SecretStr(azure_api_key),
        azure_deployment="gpt-4o",
        api_version="2024-02-01",
        temperature=temperature if temperature is not None else 0.7,
    )

    logger.debug("🤖 Azure OpenAI GPT实例创建完成")
    return llm
