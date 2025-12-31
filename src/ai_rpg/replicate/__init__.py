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
    run_concurrent_tasks,
    # 任务类
    ImageGenerationSubTask,
    ImageDownloadSubTask,
    ReplicateImageTask,
)
from .types import ReplicateImageInput

__all__ = [
    "ReplicateConfig",
    # "load_replicate_config",
    "test_replicate_api_connection",
    "run_concurrent_tasks",
    # 任务类
    "ImageGenerationSubTask",
    "ImageDownloadSubTask",
    "ReplicateImageTask",
    "ReplicateImageInput",
    "replicate_config",
    "DEFAULT_OUTPUT_DIR",
]
