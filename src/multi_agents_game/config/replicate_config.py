#!/usr/bin/env python3
"""
Replicate 配置管理模块
统一管理 Replicate API 配置、模型配置和初始化逻辑
"""

import os
from pathlib import Path
from typing import Any, Final, Optional

from loguru import logger
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

# 加载环境变量
load_dotenv()

# 常量定义
TEST_URL: Final[str] = "https://api.replicate.com/v1/models"


def test_replicate_api_connection() -> bool:
    """
    测试 Replicate API 连接
    独立函数，不依赖配置类实例

    Returns:
        bool: 连接成功返回 True，失败返回 False
    """
    api_token = os.getenv("REPLICATE_API_TOKEN")
    if not api_token:
        print("❌ API Token 未配置")
        return False

    headers = {"Authorization": f"Token {api_token}"}

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


# Pydantic 数据模型定义
class ModelInfo(BaseModel):
    """单个模型信息的数据结构"""

    version: str = Field(..., description="模型版本ID")
    cost_estimate: str = Field(..., description="成本估算描述")
    description: str = Field(..., description="模型描述")

    model_config = ConfigDict(extra="forbid")  # 禁止额外字段


class ImageModels(BaseModel):
    """图像模型配置数据结构"""

    sdxl_lightning: Optional[ModelInfo] = Field(None, alias="sdxl-lightning")
    sdxl: Optional[ModelInfo] = None
    playground: Optional[ModelInfo] = None
    realvis: Optional[ModelInfo] = None
    ideogram_v3_turbo: Optional[ModelInfo] = Field(None, alias="ideogram-v3-turbo")

    model_config = ConfigDict(
        populate_by_name=True,  # 修复: 使用新的参数名
        extra="allow",  # 允许额外的图像模型
    )

    def model_post_init(self, __context: Any) -> None:
        """验证额外字段也符合ModelInfo格式"""
        for field_name, field_value in self.__dict__.items():
            if field_name not in self.model_fields and field_value is not None:
                if isinstance(field_value, dict):
                    # 验证额外的模型是否符合ModelInfo格式
                    ModelInfo(**field_value)


class ChatModels(BaseModel):
    """对话模型配置数据结构"""

    gpt_4o_mini: Optional[ModelInfo] = Field(None, alias="gpt-4o-mini")
    gpt_4o: Optional[ModelInfo] = Field(None, alias="gpt-4o")
    claude_3_5_sonnet: Optional[ModelInfo] = Field(None, alias="claude-3.5-sonnet")
    llama_3_1_405b: Optional[ModelInfo] = Field(None, alias="llama-3.1-405b")
    llama_3_70b: Optional[ModelInfo] = Field(None, alias="llama-3-70b")

    model_config = ConfigDict(
        populate_by_name=True,  # 修复: 使用新的参数名
        extra="allow",  # 允许额外的对话模型
    )

    def model_post_init(self, __context: Any) -> None:
        """验证额外字段也符合ModelInfo格式"""
        for field_name, field_value in self.__dict__.items():
            if field_name not in self.model_fields and field_value is not None:
                if isinstance(field_value, dict):
                    # 验证额外的模型是否符合ModelInfo格式
                    ModelInfo(**field_value)


class ReplicateModelsConfig(BaseModel):
    """Replicate模型配置的完整数据结构"""

    image_models: ImageModels = Field(..., description="图像生成模型配置")
    chat_models: ChatModels = Field(..., description="对话模型配置")

    model_config = ConfigDict(extra="forbid")  # 严格模式，不允许额外字段



def load_replicate_config(config_path: Path) -> ReplicateModelsConfig:
    """
    加载MCP配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        McpConfig: MCP配置对象

    Raises:
        RuntimeError: 配置加载失败时抛出
    """
    try:
        assert config_path.exists(), f"{config_path} not found"
        mcp_config = ReplicateModelsConfig.model_validate_json(
            config_path.read_text(encoding="utf-8")
        )

        logger.info(f"MCP Config loaded from {config_path}: {mcp_config}")

        return mcp_config
    except Exception as e:
        logger.error(f"Error loading MCP config: {e}")
        raise RuntimeError("Failed to load MCP config")
