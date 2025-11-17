"""
Dungeon 相关的 MongoDB 文档模型和存储操作
"""

import gzip
from datetime import datetime
from typing import final
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from loguru import logger
from ..models.dungeon import Dungeon
from .client import mongo_upsert_one, mongo_find_one


###############################################################################################################################################
@final
class DungeonDocument(BaseModel):
    """
    MongoDB 文档模型：地下城运行时状态（Dungeon）

    用于存储地下城的运行时状态到 MongoDB 中。
    Dungeon 是动态的运行时数据，会随着游戏进程不断变化。
    使用 gzip 压缩存储以节省空间，每次 save_world 都会更新。
    """

    # Pydantic V2 配置
    model_config = ConfigDict(
        populate_by_name=True,  # 允许使用字段别名（如 _id）
        arbitrary_types_allowed=True,  # 允许任意类型（bytes）
    )

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        alias="_id",
        description="文档唯一标识符，使用 UUID",
    )
    world_id: str = Field(..., description="关联的 World 文档 ID (1:1 关系)")
    dungeon_compressed: bytes = Field(..., description="gzip 压缩的 Dungeon JSON 数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="更新时间戳")


###############################################################################################################################################
def save_dungeon(dungeon: Dungeon, world_id: str) -> str:
    """
    存储 Dungeon 对象到 MongoDB（gzip 压缩）

    参数:
        dungeon: Dungeon 对象
        world_id: 关联的 World 文档 ID

    返回:
        str: DungeonDocument 的 ID

    说明:
        - 检查 Dungeon 是否有效（name 不为空）
        - 使用 model_dump_json() 序列化为 JSON
        - 使用 gzip 压缩 JSON 数据
        - **每次都执行 upsert 更新**（与 Boot 不同，Dungeon 是运行时数据）
        - 如果 Dungeon 无效（name 为空），返回空字符串
    """
    try:
        # 检查 Dungeon 是否有效
        if not dungeon.name or dungeon.name == "":
            logger.info(f"Dungeon 无效（name 为空），跳过存储: world_id={world_id}")
            return ""

        # 序列化为 JSON
        dungeon_json = dungeon.model_dump_json()

        # gzip 压缩
        dungeon_compressed = gzip.compress(dungeon_json.encode("utf-8"))

        # 查询是否已存在 DungeonDocument
        existing_doc = mongo_find_one("dungeons", filter_dict={"world_id": world_id})

        if existing_doc:
            # 已存在，使用现有 ID 进行更新
            dungeon_id = str(existing_doc.get("_id", ""))
            logger.debug(f"更新已存在的 Dungeon: ID={dungeon_id}")
        else:
            # 不存在，创建新 ID
            dungeon_id = str(uuid4())
            logger.debug(f"创建新的 Dungeon: ID={dungeon_id}")

        # 创建 DungeonDocument
        dungeon_doc = DungeonDocument(
            _id=dungeon_id,
            world_id=world_id,
            dungeon_compressed=dungeon_compressed,
        )

        # 存储到 MongoDB（upsert：存在则更新，不存在则插入）
        doc_dict = dungeon_doc.model_dump(by_alias=True)
        result_id = mongo_upsert_one("dungeons", doc_dict, filter_key="_id")

        if not result_id:
            raise RuntimeError(f"存储 DungeonDocument 失败")

        compressed_size = len(dungeon_compressed)
        original_size = len(dungeon_json.encode("utf-8"))
        compression_ratio = (
            (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        )

        logger.info(
            f"存储 Dungeon 成功: ID={dungeon_id}, world_id={world_id}, "
            f"原始大小={original_size} bytes, "
            f"压缩后={compressed_size} bytes, "
            f"压缩率={compression_ratio:.1f}%"
        )

        return dungeon_id

    except Exception as e:
        logger.error(f"存储 Dungeon 失败: {e}")
        raise


###############################################################################################################################################
def load_dungeon(world_id: str) -> Dungeon:
    """
    从 MongoDB 加载 Dungeon 对象（gzip 解压）

    参数:
        world_id: 关联的 World 文档 ID

    返回:
        Dungeon: 还原的 Dungeon 对象，如果不存在则返回默认 Dungeon(name="")

    说明:
        - 根据 world_id 查询 DungeonDocument
        - 如果不存在，返回默认 Dungeon
        - 使用 gzip 解压数据
        - 使用 model_validate_json() 还原 Dungeon 对象
    """
    try:
        # 查询 DungeonDocument
        dungeon_doc_dict = mongo_find_one(
            "dungeons", filter_dict={"world_id": world_id}
        )

        if not dungeon_doc_dict:
            logger.info(f"未找到 Dungeon 文档: world_id={world_id}，返回默认 Dungeon")
            return Dungeon(name="")

        dungeon_id = dungeon_doc_dict.get("_id")
        dungeon_compressed = dungeon_doc_dict.get("dungeon_compressed")

        if not dungeon_compressed:
            logger.warning(f"Dungeon 文档数据为空: dungeon_id={dungeon_id}")
            return Dungeon(name="")

        # gzip 解压
        dungeon_json_bytes = gzip.decompress(dungeon_compressed)
        dungeon_json = dungeon_json_bytes.decode("utf-8")

        # 还原 Dungeon 对象
        dungeon = Dungeon.model_validate_json(dungeon_json)

        logger.info(
            f"加载 Dungeon 成功: dungeon_id={dungeon_id}, world_id={world_id}, "
            f"dungeon.name={dungeon.name}"
        )

        return dungeon

    except Exception as e:
        logger.error(f"加载 Dungeon 失败: {e}")
        raise


###############################################################################################################################################
