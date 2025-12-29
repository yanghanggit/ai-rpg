from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

from typing import Optional
import os
from pydantic import SecretStr
from langchain_deepseek import ChatDeepSeek
from loguru import logger


def create_deepseek_chat(temperature: Optional[float] = None) -> ChatDeepSeek:
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


def create_deepseek_reasoner(temperature: Optional[float] = None) -> ChatDeepSeek:
    """
    创建新的DeepSeek Reasoner实例（思考模式）

    注意：此模型为DeepSeek-V3.2的思考模式，具有以下特性：
    - 启用推理思考过程，适合复杂推理任务
    - 更大的输出token限制（默认32K，最大64K）
    - ⚠️ 不支持工具调用（Tool Calls）
    - ⚠️ 不支持结构化输出（Structured Output）
    - 如需工具调用或结构化输出，请使用 create_deepseek_chat()

    Args:
        temperature: 可选的温度参数，控制输出随机性。默认为0.7

    Returns:
        ChatDeepSeek: 新创建的DeepSeek Reasoner实例

    Raises:
        ValueError: 当DEEPSEEK_API_KEY环境变量未设置时
    """
    logger.debug("🧠 创建新的DeepSeek Reasoner实例（思考模式）...")

    # 检查必需的环境变量
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

    # 创建Reasoner模型实例
    llm = ChatDeepSeek(
        api_key=SecretStr(deepseek_api_key),
        api_base="https://api.deepseek.com/v1",
        model="deepseek-reasoner",
        temperature=temperature if temperature is not None else 0.7,
        # Reasoner模式不支持结构化输出和工具调用
    )

    logger.debug("🧠 DeepSeek Reasoner实例创建完成")
    return llm
