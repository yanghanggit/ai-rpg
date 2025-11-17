"""
Boot 相关的 MongoDB 文档模型和存储操作
"""

import gzip
from datetime import datetime
from typing import final
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from loguru import logger
from ..models.world import Boot
from .client import mongo_upsert_one, mongo_find_one


###############################################################################################################################################
@final
class BootDocument(BaseModel):
    """
    MongoDB 文档模型：游戏世界启动配置（Boot）

    用于存储游戏世界的种子文件（Boot）到 MongoDB 中。
    Boot 是静态的世界观配置，只在创建时使用一次，不会变化。
    使用 gzip 压缩存储以节省空间，即使压缩后接近 16MB 也是合理的。
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
    boot_compressed: bytes = Field(..., description="gzip 压缩的 Boot JSON 数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="创建时间戳")


###############################################################################################################################################
def save_boot(boot: Boot, world_id: str) -> str:
    """
    存储 Boot 对象到 MongoDB（gzip 压缩）

    参数:
        boot: Boot 对象
        world_id: 关联的 World 文档 ID

    返回:
        str: BootDocument 的 ID

    说明:
        - 检查 Boot 是否有效（name 不为空）
        - 使用 model_dump_json() 序列化为 JSON
        - 使用 gzip 压缩 JSON 数据
        - 存储到 boots 集合
        - 如果 Boot 无效（name 为空），返回空字符串
    """
    try:
        # 检查 Boot 是否有效
        if not boot.name or boot.name == "":
            logger.info(f"Boot 无效（name 为空），跳过存储: world_id={world_id}")
            return ""

        # 序列化为 JSON
        boot_json = boot.model_dump_json()

        # gzip 压缩
        boot_compressed = gzip.compress(boot_json.encode("utf-8"))

        # 创建 BootDocument
        boot_doc = BootDocument(
            world_id=world_id,
            boot_compressed=boot_compressed,
        )

        boot_id = boot_doc.id

        # 存储到 MongoDB
        doc_dict = boot_doc.model_dump(by_alias=True)
        result_id = mongo_upsert_one("boots", doc_dict, filter_key="_id")

        if not result_id:
            raise RuntimeError(f"存储 BootDocument 失败")

        compressed_size = len(boot_compressed)
        original_size = len(boot_json.encode("utf-8"))
        compression_ratio = (
            (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        )

        logger.info(
            f"存储 Boot 成功: ID={boot_id}, world_id={world_id}, "
            f"原始大小={original_size} bytes, "
            f"压缩后={compressed_size} bytes, "
            f"压缩率={compression_ratio:.1f}%"
        )

        return boot_id

    except Exception as e:
        logger.error(f"存储 Boot 失败: {e}")
        raise


###############################################################################################################################################
def load_boot(world_id: str) -> Boot:
    """
    从 MongoDB 加载 Boot 对象（gzip 解压）

    参数:
        world_id: 关联的 World 文档 ID

    返回:
        Boot: 还原的 Boot 对象，如果不存在则返回默认 Boot(name="")

    说明:
        - 根据 world_id 查询 BootDocument
        - 如果不存在，返回默认 Boot
        - 使用 gzip 解压数据
        - 使用 model_validate_json() 还原 Boot 对象
    """
    try:
        # 查询 BootDocument
        boot_doc_dict = mongo_find_one("boots", filter_dict={"world_id": world_id})

        if not boot_doc_dict:
            logger.info(f"未找到 Boot 文档: world_id={world_id}，返回默认 Boot")
            return Boot(name="")

        boot_id = boot_doc_dict.get("_id")
        boot_compressed = boot_doc_dict.get("boot_compressed")

        if not boot_compressed:
            logger.warning(f"Boot 文档数据为空: boot_id={boot_id}")
            return Boot(name="")

        # gzip 解压
        boot_json_bytes = gzip.decompress(boot_compressed)
        boot_json = boot_json_bytes.decode("utf-8")

        # 还原 Boot 对象
        boot = Boot.model_validate_json(boot_json)

        logger.info(
            f"加载 Boot 成功: boot_id={boot_id}, world_id={world_id}, "
            f"boot.name={boot.name}"
        )

        return boot

    except Exception as e:
        logger.error(f"加载 Boot 失败: {e}")
        raise


###############################################################################################################################################
