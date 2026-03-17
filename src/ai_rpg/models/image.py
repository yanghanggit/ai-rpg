from typing import final
from pydantic import BaseModel, Field


###############################################################################################################################################
@final
class GeneratedImage(BaseModel):
    """AI 文生图生成的图片资产（通用模型）"""

    filename: str = Field(default="", description="文件名")
    url: str = Field(default="", description="访问 URL（相对路径）")
    prompt: str = Field(default="", description="使用的提示词")
    model: str = Field(default="", description="使用的模型")
    local_path: str = Field(default="", description="本地存储路径")
