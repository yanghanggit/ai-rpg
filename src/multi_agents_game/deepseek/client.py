from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
from typing import Optional
from pydantic import SecretStr
from langchain_deepseek import ChatDeepSeek


# 全局DeepSeek LLM实例（懒加载单例）
_global_deepseek_llm: Optional[ChatDeepSeek] = None


def get_deepseek_llm() -> ChatDeepSeek:
    """
    获取全局DeepSeek LLM实例（懒加载单例模式）

    Returns:
        ChatDeepSeek: 配置好的DeepSeek LLM实例

    Raises:
        ValueError: 当DEEPSEEK_API_KEY环境变量未设置时
    """
    global _global_deepseek_llm

    if _global_deepseek_llm is None:
        logger.info("🤖 初始化全局DeepSeek LLM实例...")

        # 检查必需的环境变量
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        if not deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

        _global_deepseek_llm = ChatDeepSeek(
            api_key=SecretStr(deepseek_api_key),
            model="deepseek-chat",
            temperature=0.7,
        )

        logger.success("🤖 全局DeepSeek LLM实例创建完成")

    return _global_deepseek_llm
