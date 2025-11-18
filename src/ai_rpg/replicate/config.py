#!/usr/bin/env python3
"""
Replicate 配置管理模块
统一管理 Replicate API 配置、模型配置和初始化逻辑
"""

from pathlib import Path
from typing import Dict, Final, Optional


# 默认输出目录
DEFAULT_OUTPUT_DIR: Final[Path] = Path("generated_images")


# Replicate 配置类
class ReplicateConfig:
    """Replicate模型配置 - 简化版本，直接硬编码模型信息"""

    def __init__(self) -> None:
        """初始化配置"""
        # 默认使用的图像生成模型
        self.default_image_model: str = "ideogram-v3-turbo"

        # 模型版本映射
        self.image_models: Dict[str, Dict[str, str]] = {
            "ideogram-v3-turbo": {
                "version": "ideogram-ai/ideogram-v3-turbo:32a9584617b239dd119c773c8c18298d310068863d26499e6199538e9c29a586",
            }
        }

    def get_model_version(self, model_name: Optional[str] = None) -> str:
        """
        获取模型版本

        Args:
            model_name: 模型名称，如果为None则使用默认模型

        Returns:
            模型版本字符串

        Raises:
            ValueError: 不支持的模型名称
        """
        if model_name is None:
            model_name = self.default_image_model

        if model_name not in self.image_models:
            raise ValueError(
                f"不支持的模型: {model_name}. 可用模型: {list(self.image_models.keys())}"
            )

        return self.image_models[model_name]["version"]

    def get_available_models(self) -> Dict[str, Dict[str, str]]:
        """
        获取所有可用的图像模型配置

        Returns:
            模型配置字典
        """
        return self.image_models


replicate_config: Final[ReplicateConfig] = ReplicateConfig()
