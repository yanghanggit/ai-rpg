"""
MongoDB Document Models

This module contains Pydantic BaseModel classes for MongoDB document structures.
These models provide type safety, validation, and serialization for MongoDB operations.

Author: yanghanggit
Date: 2025-07-30
"""

import gzip
import json
from datetime import datetime
from typing import Any, Dict, final
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from ..models.world import World
from loguru import logger


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
    game_name: str = Field(..., description="游戏名称")
    timestamp: datetime = Field(default_factory=datetime.now, description="创建时间戳")
    version: str = Field(default="1.0.0", description="版本号")
    world_data_compressed: bytes = Field(
        ..., description="压缩后的游戏世界数据（gzip）"
    )

    # Pydantic V2 配置
    model_config = ConfigDict(
        populate_by_name=True,  # 允许使用字段别名（如 _id）
        arbitrary_types_allowed=True,  # 允许任意类型（如果需要）
    )

    @property
    def world_data(self) -> World:
        """
        获取解压缩后的游戏世界数据

        Returns:
            World: 解压缩后的游戏世界对象
        """
        return self._decompress_world_data(self.world_data_compressed)

    @staticmethod
    def _compress_world_data(world: World) -> bytes:
        """
        压缩 World 对象为 gzip 字节数据

        Args:
            world: 要压缩的 World 对象

        Returns:
            bytes: 压缩后的字节数据
        """
        json_str = world.model_dump_json()
        compressed_data = gzip.compress(json_str.encode("utf-8"))

        # 检查压缩后数据大小，MongoDB 文档限制为 16MB
        if len(compressed_data) > 15 * 1024 * 1024:
            logger.error(
                f"警告: 压缩后的世界数据大小 {len(compressed_data) / (1024 * 1024):.2f}MB 即将超过 MongoDB 16MB 限制！"
            )

        return compressed_data

    @staticmethod
    def _decompress_world_data(compressed_data: bytes) -> World:
        """
        解压缩字节数据为 World 对象

        Args:
            compressed_data: 压缩的字节数据

        Returns:
            World: 解压缩后的 World 对象
        """
        json_str = gzip.decompress(compressed_data).decode("utf-8")
        world_dict = json.loads(json_str)
        return World(**world_dict)

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        """序列化时间戳为 ISO 格式字符串"""
        return value.isoformat()

    @classmethod
    def create_from_world(
        cls, username: str, world: World, version: str
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
        compressed_data = cls._compress_world_data(world)
        return cls(
            username=username,
            game_name=world.boot.name,
            version=version,
            world_data_compressed=compressed_data,
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式，用于 MongoDB 存储

        注意：world_data_compressed 字段包含 gzip 压缩的游戏世界数据

        Returns:
            dict: 包含所有字段的字典，使用 MongoDB 的 _id 字段名
        """
        data = self.model_dump(by_alias=True)
        return data

    # 便捷方法
    @classmethod
    def from_mongo(cls, mongodb_doc: Dict[str, Any]) -> "WorldDocument":
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


###############################################################################################################################################
