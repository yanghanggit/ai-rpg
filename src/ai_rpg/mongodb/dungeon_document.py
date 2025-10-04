"""
MongoDB Document Models

This module contains Pydantic BaseModel classes for MongoDB document structures.
These models provide type safety, validation, and serialization for MongoDB operations.

Author: yanghanggit
Date: 2025-10-04
"""

from datetime import datetime
from typing import Any, Dict, final
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from ..models.dungeon import Dungeon


###############################################################################################################################################
@final
class DungeonDocument(BaseModel):
    """
    MongoDB 文档模型：地下城数据

    用于存储地下城数据到 MongoDB 中，包含游戏名称、时间戳、版本和地下城数据。
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        alias="_id",
        description="文档唯一标识符，使用 UUID",
    )
    dungeon_name: str = Field(..., description="地下城名称")
    timestamp: datetime = Field(default_factory=datetime.now, description="创建时间戳")
    version: str = Field(default="1.0.0", description="版本号")
    dungeon_data: Dungeon = Field(..., description="地下城数据")

    # Pydantic V2 配置
    model_config = ConfigDict(
        populate_by_name=True,  # 允许使用字段别名（如 _id）
        arbitrary_types_allowed=True,  # 允许任意类型（如果需要）
    )

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        """序列化时间戳为 ISO 格式字符串"""
        return value.isoformat()

    @classmethod
    def create_from_dungeon(cls, dungeon: Dungeon, version: str) -> "DungeonDocument":
        """
        从 Dungeon 对象创建 DungeonDocument 实例

        Args:
            dungeon: Dungeon 地下城对象
            version: 版本号，默认为 "1.0.0"

        Returns:
            DungeonDocument: 创建的文档实例
        """
        return cls(dungeon_name=dungeon.name, version=version, dungeon_data=dungeon)

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
    def from_mongodb(cls, mongodb_doc: Dict[str, Any]) -> "DungeonDocument":
        """
        从 MongoDB 文档创建 DungeonDocument 实例

        Args:
            mongodb_doc: 从 MongoDB 获取的原始文档字典

        Returns:
            DungeonDocument: 反序列化的文档实例

        Raises:
            ValueError: 当文档格式不正确时
        """
        try:
            return cls(**mongodb_doc)
        except Exception as e:
            raise ValueError(f"无法从 MongoDB 文档创建 DungeonDocument: {e}") from e


###############################################################################################################################################
