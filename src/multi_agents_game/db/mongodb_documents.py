"""
MongoDB Document Models

This module contains Pydantic BaseModel classes for MongoDB document structures.
These models provide type safety, validation, and serialization for MongoDB operations.

Author: yanghanggit
Date: 2025-07-30
"""

from datetime import datetime
from typing import final, Dict, Any
from uuid import uuid4
from pydantic import BaseModel, Field
from ..models.world import Boot


###############################################################################################################################################
@final
class WorldBootDocument(BaseModel):
    """
    MongoDB 文档模型：游戏世界启动配置

    用于存储游戏世界的启动配置信息到 MongoDB 中，包含游戏名称、时间戳、版本和启动数据。
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        alias="_id",
        description="文档唯一标识符，使用 UUID",
    )
    game_name: str = Field(..., description="游戏名称")
    timestamp: datetime = Field(default_factory=datetime.now, description="创建时间戳")
    version: str = Field(default="1.0.0", description="版本号")
    boot_data: Boot = Field(..., description="游戏世界启动配置数据")

    class Config:
        """Pydantic 配置"""

        populate_by_name = True  # 允许使用字段别名（如 _id）
        json_encoders = {datetime: lambda v: v.isoformat()}  # 自定义 datetime 序列化

    @classmethod
    def create_from_boot(
        cls, game_name: str, boot: Boot, version: str = "1.0.0"
    ) -> "WorldBootDocument":
        """
        从 Boot 对象创建 WorldBootDocument 实例

        Args:
            game_name: 游戏名称
            boot: Boot 启动配置对象
            version: 版本号，默认为 "1.0.0"

        Returns:
            WorldBootDocument: 创建的文档实例
        """
        return cls(game_name=game_name, version=version, boot_data=boot)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式，用于 MongoDB 存储

        Returns:
            dict: 包含所有字段的字典，使用 MongoDB 的 _id 字段名
        """
        data = self.model_dump(by_alias=True)
        return data

    @property
    def document_id(self) -> str:
        """获取文档 ID"""
        return self.id

    @property
    def stages_count(self) -> int:
        """获取场景数量"""
        return len(self.boot_data.stages)

    @property
    def actors_count(self) -> int:
        """获取角色数量"""
        return len(self.boot_data.actors)

    @property
    def world_systems_count(self) -> int:
        """获取世界系统数量"""
        return len(self.boot_data.world_systems)


###############################################################################################################################################
