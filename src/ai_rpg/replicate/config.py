#!/usr/bin/env python3
"""
Replicate 配置管理模块
统一管理 Replicate API 配置、模型配置和初始化逻辑
"""

from pathlib import Path
from typing import Dict, Final, Optional


# 默认输出目录
GENERATED_IMAGES_OUTPUT_DIR: Final[Path] = Path("generated_images")
GENERATED_IMAGES_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
assert GENERATED_IMAGES_OUTPUT_DIR.exists(), "无法创建默认输出目录"

# 静态文件服务的 HTTP URL 前缀（与 run_game_server.py 的 app.mount 保持一致）
GENERATED_IMAGES_URL_PREFIX: Final[str] = "/images"
assert GENERATED_IMAGES_URL_PREFIX.startswith("/"), "URL 前缀必须以 / 开头"

"""
## 📋 Nano-Banana 模型支持的所有尺寸

**Gemini 2.5 Flash Image (nano-banana)** 支持以下宽高比和对应分辨率：

| 宽高比 | 分辨率 (像素) | Token 消耗 | 适用场景 |
| ------ | ------------- | ---------- | -------- |
| **1:1** | 1024 x 1024 | 1290 | 正方形，社交媒体、头像、图标 |
| **2:3** | 832 x 1248 | 1290 | 竖屏，手机壁纸、竖版海报 |
| **3:2** | 1248 x 832 | 1290 | 横屏，传统摄影比例 |
| **3:4** | 864 x 1184 | 1290 | 竖屏，海报、宣传册 |
| **4:3** | 1184 x 864 | 1290 | 横屏，传统显示器比例 |
| **4:5** | 896 x 1152 | 1290 | 竖屏，Instagram 帖子 |
| **5:4** | 1152 x 896 | 1290 | 横屏，经典显示器比例 |
| **9:16** | 768 x 1344 | 1290 | 竖屏，手机全屏、Stories、短视频 |
| **16:9** | 1344 x 768 | 1290 | 横屏，宽屏视频、桌面壁纸 |
| **21:9** | 1536 x 672 | 1290 | 超宽屏，电影比例、超宽显示器 |

**说明：**

- 所有尺寸的 Token 消耗相同（1290 tokens）
- 默认分辨率等级：1K（1024 像素级别）
- 图片格式：PNG（自动添加 SynthID 水印）
- 推荐使用原生支持的宽高比以获得最佳效果
- 如不指定宽高比，默认生成 1:1 正方形图片
"""


# Replicate 配置类
class ReplicateConfig:
    """Replicate模型配置 - 简化版本，直接硬编码模型信息"""

    def __init__(self) -> None:
        """初始化配置"""
        # 默认使用的图像生成模型
        self.default_image_model: str = "nano-banana"

        # 模型版本映射
        self.image_models: Dict[str, Dict[str, str]] = {
            "ideogram-v3-turbo": {
                "version": "ideogram-ai/ideogram-v3-turbo:32a9584617b239dd119c773c8c18298d310068863d26499e6199538e9c29a586",
            },
            "stable-diffusion-3.5-large": {
                "version": "stability-ai/stable-diffusion-3.5-large",
            },  # 由于 SD 3.5 不支持中文!
            "flux-schnell": {
                "version": "black-forest-labs/flux-schnell",
            },  # 1-4步极速生成，Apache 2.0开源，成本极低($0.003/张)
            "nano-banana": {
                "version": "google/nano-banana",
            },  # Google Gemini 2.5 图像生成和编辑模型，$0.039/张
            "nano-banana-pro": {
                "version": "google/nano-banana-pro",
            },  # Google Gemini 3 Pro 图像生成，支持4K，$0.15-0.30/张
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
