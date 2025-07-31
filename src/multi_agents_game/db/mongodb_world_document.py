"""
MongoDB Document Models

This module contains Pydantic BaseModel classes for MongoDB document structures.
These models provide type safety, validation, and serialization for MongoDB operations.

Author: yanghanggit
Date: 2025-07-30
"""

import json
from datetime import datetime
from pathlib import Path
from typing import final, Dict, Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from ..models.world import World


###############################################################################################################################################
@final
class WorldDocument(BaseModel):
    """
    MongoDB 文档模型：游戏世界启动配置

    用于存储游戏世界的启动配置信息到 MongoDB 中，包含游戏名称、时间戳、版本和启动数据。
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        alias="_id",
        description="文档唯一标识符，使用 UUID",
    )
    username: str = Field(..., description="用户名")
    timestamp: datetime = Field(default_factory=datetime.now, description="创建时间戳")
    version: str = Field(default="1.0.0", description="版本号")
    world_data: World = Field(..., description="游戏世界启动配置数据")

    # Pydantic V2 配置
    model_config = ConfigDict(
        populate_by_name=True,  # 允许使用字段别名（如 _id）
        arbitrary_types_allowed=True,  # 允许任意类型（如果需要）
    )

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        """序列化时间戳为 ISO 格式字符串"""
        return value.isoformat()

    @classmethod
    def create_from_world(
        cls, username: str, world: World, version: str = "1.0.0"
    ) -> "WorldDocument":
        """
        从 World 对象创建 WorldDocument 实例

        Args:
            username: 用户名
            world: World 对象
            version: 版本号，默认为 "1.0.0"

        Returns:
            WorldDocument: 创建的文档实例
        """
        return cls(username=username, version=version, world_data=world)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式，用于 MongoDB 存储

        Returns:
            dict: 包含所有字段的字典，使用 MongoDB 的 _id 字段名
        """
        data = self.model_dump(by_alias=True)
        return data

    # 便捷方法
    @classmethod
    def from_mongodb(cls, mongodb_doc: Dict[str, Any]) -> "WorldDocument":
        """
        从 MongoDB 文档创建 WorldDocument 实例

        Args:
            mongodb_doc: 从 MongoDB 获取的原始文档字典

        Returns:
            WorldDocument: 反序列化的文档实例

        Raises:
            ValueError: 当文档格式不正确时
        """
        try:
            return cls(**mongodb_doc)
        except Exception as e:
            raise ValueError(f"无法从 MongoDB 文档创建 WorldDocument: {e}") from e

    def save_world_to_file(self, file_path: Optional[Path] = None) -> Path:
        """
        将 World 数据保存到 JSON 文件

        Args:
            file_path: 保存路径，如果为 None 则使用游戏名称作为文件名

        Returns:
            Path: 保存的文件路径

        Raises:
            OSError: 当文件写入失败时
        """
        if file_path is None:
            file_path = Path(f"{self.username}-{self.world_data.boot.name}.json")

        try:
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 保存 World 数据到文件
            world_dict = self.world_data.model_dump()
            file_path.write_text(
                json.dumps(world_dict, ensure_ascii=False, indent=4), encoding="utf-8"
            )

            return file_path
        except Exception as e:
            raise OSError(f"保存 World 数据到文件失败: {e}") from e


###############################################################################################################################################
