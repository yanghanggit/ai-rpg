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

    # 便捷方法
    @classmethod
    def from_mongodb(cls, mongodb_doc: Dict[str, Any]) -> "WorldBootDocument":
        """
        从 MongoDB 文档创建 WorldBootDocument 实例

        Args:
            mongodb_doc: 从 MongoDB 获取的原始文档字典

        Returns:
            WorldBootDocument: 反序列化的文档实例

        Raises:
            ValueError: 当文档格式不正确时
        """
        try:
            return cls(**mongodb_doc)
        except Exception as e:
            raise ValueError(f"无法从 MongoDB 文档创建 WorldBootDocument: {e}") from e

    def save_boot_to_file(self, file_path: Optional[Path] = None) -> Path:
        """
        将 Boot 数据保存到 JSON 文件

        Args:
            file_path: 保存路径，如果为 None 则使用游戏名称作为文件名

        Returns:
            Path: 保存的文件路径

        Raises:
            OSError: 当文件写入失败时
        """
        if file_path is None:
            file_path = Path(f"{self.game_name}.json")

        try:
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 保存 Boot 数据到文件
            boot_dict = self.boot_data.model_dump()
            file_path.write_text(
                json.dumps(boot_dict, ensure_ascii=False, indent=4), encoding="utf-8"
            )

            return file_path
        except Exception as e:
            raise OSError(f"保存 Boot 数据到文件失败: {e}") from e

    def get_summary(self) -> Dict[str, Any]:
        """
        获取文档摘要信息

        Returns:
            dict: 包含关键统计信息的摘要
        """
        return {
            "document_id": self.document_id,
            "game_name": self.game_name,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "boot_name": self.boot_data.name,
            "campaign_setting": self.boot_data.campaign_setting,
            "stages_count": self.stages_count,
            "actors_count": self.actors_count,
            "world_systems_count": self.world_systems_count,
            "total_size_estimate": len(json.dumps(self.to_dict(), default=str)),
        }

    def validate_integrity(self) -> bool:
        """
        验证文档数据完整性

        Returns:
            bool: 如果数据完整性验证通过返回 True，否则返回 False
        """
        try:
            # 检查基本字段
            if not self.game_name or not self.boot_data.name:
                return False

            # 检查 Boot 数据结构
            if not hasattr(self.boot_data, "stages") or not hasattr(
                self.boot_data, "actors"
            ):
                return False

            # 检查列表不为空（根据业务需求）
            if self.stages_count == 0:
                return False

            return True
        except Exception:
            return False

    def update_version(self, new_version: str) -> "WorldBootDocument":
        """
        更新版本号并返回新的实例

        Args:
            new_version: 新的版本号

        Returns:
            WorldBootDocument: 更新版本后的新实例
        """
        return self.model_copy(
            update={"version": new_version, "timestamp": datetime.now()}
        )


###############################################################################################################################################
