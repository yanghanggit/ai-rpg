#!/usr/bin/env python3
"""
Replicate 模块
统一管理 Replicate API 相关功能
"""

from .client import ReplicateImageRequest
from .config import (
    GENERATED_IMAGES_OUTPUT_DIR,
    GENERATED_IMAGES_URL_PREFIX,
    ReplicateConfig,
    replicate_config,
)
from .connection import check_replicate_connection
from .schemas import ReplicateImageInput
from .tasks import (
    ImageDownloadTask,
    ImageGenerationTask,
    ReplicateImageTask,
    generate_images_concurrently,
)

__all__ = [
    "ReplicateConfig",
    "check_replicate_connection",
    "generate_images_concurrently",
    "ImageGenerationTask",
    "ImageDownloadTask",
    "ReplicateImageTask",
    "ReplicateImageInput",
    "replicate_config",
    "GENERATED_IMAGES_OUTPUT_DIR",
    "GENERATED_IMAGES_URL_PREFIX",
    "ReplicateImageRequest",
]
