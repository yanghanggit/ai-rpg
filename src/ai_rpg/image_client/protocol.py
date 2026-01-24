"""
图片生成 API 模型定义
用于 Replicate 图片生成服务的请求和响应模型
"""

from typing import List, Optional, final
from pydantic import BaseModel, ConfigDict, Field


################################################################################################################
################################################################################################################
################################################################################################################


@final
class ImageGenerationConfig(BaseModel):
    """单张图片生成配置 - 对应一个完整的生成任务"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # 必需参数
    prompt: str = Field(..., description="文本提示词")

    # 模型选择
    model: Optional[str] = Field(None, description="模型名称，如不指定则使用默认模型")

    # 通用参数
    negative_prompt: str = Field(
        default="worst quality, low quality, blurry", description="负向提示词"
    )
    num_inference_steps: int = Field(default=4, ge=1, le=50, description="推理步数")
    guidance_scale: float = Field(default=7.5, ge=1.0, le=20.0, description="引导比例")

    # 尺寸参数
    width: int = Field(default=1024, ge=256, le=2048, description="图片宽度")
    height: int = Field(default=1024, ge=256, le=2048, description="图片高度")
    aspect_ratio: Optional[str] = Field(
        None, description="宽高比 (如 '1:1', '16:9')，优先级高于 width/height"
    )

    # 其他可选参数
    scheduler: str = Field(default="K_EULER", description="调度器")
    seed: Optional[int] = Field(None, description="随机种子，用于复现")
    magic_prompt_option: str = Field(
        default="Auto", description="ideogram 专用: Auto/On/Off"
    )


################################################################################################################
################################################################################################################
################################################################################################################


@final
class ImageGenerationRequest(BaseModel):
    """图片生成请求模型 - 支持单张或批量生成（每个配置独立）"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    configs: List[ImageGenerationConfig] = Field(
        ..., description="图片生成配置列表，每个配置独立生成", min_length=1
    )


################################################################################################################
################################################################################################################
################################################################################################################


@final
class GeneratedImage(BaseModel):
    """单张生成图片信息"""

    filename: str = Field(..., description="文件名")
    url: str = Field(..., description="访问 URL (相对路径)")
    prompt: str = Field(..., description="使用的提示词")
    model: str = Field(..., description="使用的模型")
    local_path: str = Field(..., description="本地存储路径")


################################################################################################################
################################################################################################################
################################################################################################################


@final
class ImageGenerationResponse(BaseModel):
    """图片生成响应模型 - 支持单张或批量响应"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    images: List[GeneratedImage] = Field(
        default_factory=list, description="生成的图片列表"
    )
    elapsed_time: float = Field(..., description="总耗时(秒)")
