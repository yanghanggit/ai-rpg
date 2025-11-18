#!/usr/bin/env python3
"""
Replicate 模块
统一管理 Replicate API 相关功能
"""

from .api_test import test_replicate_api_connection
from .config import (
    ReplicateConfig,
    replicate_config,
    DEFAULT_OUTPUT_DIR,
)
from .image_tools import (
    # 异步版本
    generate_image,
    download_image,
    generate_and_download,
    generate_multiple_images,
)

__all__ = [
    "ReplicateConfig",
    # "load_replicate_config",
    "test_replicate_api_connection",
    # 异步版本
    "generate_image",
    "download_image",
    "generate_and_download",
    "generate_multiple_images",
    "replicate_config",
    "DEFAULT_OUTPUT_DIR",
]
