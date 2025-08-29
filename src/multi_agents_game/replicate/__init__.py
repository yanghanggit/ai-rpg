#!/usr/bin/env python3
"""
Replicate 模块
统一管理 Replicate API 相关功能
"""

from .config import (
    ModelInfo,
    ImageModels,
    ChatModels,
    ReplicateModelsConfig,
    load_replicate_config,
    test_replicate_api_connection,
)
from .image_tools import (
    get_default_generation_params,
    # 异步版本
    generate_image,
    download_image,
    generate_and_download,
    generate_multiple_images,
)

__all__ = [
    "ModelInfo",
    "ImageModels",
    "ChatModels",
    "ReplicateModelsConfig",
    "load_replicate_config",
    "test_replicate_api_connection",
    "get_default_generation_params",
    # 异步版本
    "generate_image",
    "download_image",
    "generate_and_download",
    "generate_multiple_images",
]
