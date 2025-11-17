"""
EntitySerialization 和 Component 的 MongoDB 文档模型

设计思路：
1. entity_serializations: 存储实体元数据（轻量级，支持快速查询）
2. entity_components: 存储完整组件内容（使用 model_dump_json 序列化）

优势：
- 突破 16MB 单文档限制
- 支持按需加载组件内容
- 保证组件数据的完整性
"""

from datetime import datetime
from typing import List, final
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from loguru import logger
from ..models.serialization import EntitySerialization, ComponentSerialization
from .client import mongo_upsert_one, mongo_find_many, mongo_insert_one


###############################################################################################################################################
@final
class ComponentMetadata(BaseModel):
    """
    组件元数据 - 存储在 EntitySerialization 中的轻量级引用
    """

    component_id: str = Field(..., description="组件ID，关联到 entity_components 集合")
    component_name: str = Field(..., description="组件名称")
    index: int = Field(..., description="组件序号，保证顺序")
    timestamp: datetime = Field(default_factory=datetime.now, description="组件时间戳")


###############################################################################################################################################
@final
class EntitySerializationDocument(BaseModel):
    """
    MongoDB 文档模型：实体序列化元数据

    存储实体的组件元数据，不包含组件的完整内容。
    实际组件内容存储在 entity_components 集合中。
    """

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        alias="_id",
        description="EntitySerialization 唯一标识符",
    )
    world_id: str = Field(..., description="关联的 World 文档 ID")
    entity_name: str = Field(..., description="实体名称")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(
        default_factory=datetime.now, description="最后更新时间"
    )
    component_count: int = Field(default=0, description="组件总数")
    components: List[ComponentMetadata] = Field(
        default_factory=list, description="组件元数据列表"
    )


###############################################################################################################################################
@final
class EntityComponentDocument(BaseModel):
    """
    MongoDB 文档模型：实体组件完整内容

    存储单个组件的完整内容，使用 model_dump_json() 序列化 ComponentSerialization 对象。
    通过 component_id 与 EntitySerialization 关联。
    """

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        alias="_id",
        description="组件唯一标识符",
    )
    entity_serialization_id: str = Field(
        ..., description="关联的 EntitySerialization 文档 ID"
    )
    world_id: str = Field(..., description="关联的 World 文档 ID")
    entity_name: str = Field(..., description="实体名称")
    component_name: str = Field(..., description="组件名称")
    index: int = Field(..., description="组件序号")
    timestamp: datetime = Field(default_factory=datetime.now, description="组件时间戳")
    component_data: str = Field(
        ...,
        description="组件完整内容的 JSON 字符串（由 component.model_dump_json() 生成）",
    )


###############################################################################################################################################
def save_entity_serializations(
    entities_serialization: List[EntitySerialization], world_id: str
) -> List[str]:
    """
    存储所有 EntitySerialization 到 MongoDB

    参数:
        entities_serialization: EntitySerialization 列表
        world_id: World 文档的 ID，用于关联 EntitySerialization

    返回:
        List[str]: 成功存储的 EntitySerialization 文档 ID 列表

    说明:
        - 将每个 EntitySerialization 存储为独立文档
        - 每个实体的组件列表会被转换为元数据引用
        - 实际组件内容存储到 entity_components 集合
    """
    saved_ids: List[str] = []

    try:
        for entity_serialization in entities_serialization:
            # 创建 EntitySerialization 文档
            entity_doc = EntitySerializationDocument(
                world_id=world_id,
                entity_name=entity_serialization.name,
                component_count=len(entity_serialization.components),
                components=[
                    ComponentMetadata(
                        component_id=f"comp_{world_id}_{entity_serialization.name}_{idx}",
                        component_name=comp.name,
                        index=idx,
                    )
                    for idx, comp in enumerate(entity_serialization.components)
                ],
            )

            # 存储 EntitySerialization 元数据
            doc_dict = entity_doc.model_dump(by_alias=True)
            result_id = mongo_upsert_one(
                "entity_serializations",
                doc_dict,
                filter_key="_id",
            )

            if result_id:
                saved_ids.append(result_id)

                # 存储每个组件的完整内容
                _save_entity_components(entity_serialization, entity_doc.id, world_id)

                logger.debug(
                    f"存储 EntitySerialization 成功: {entity_serialization.name}, "
                    f"组件数: {len(entity_serialization.components)}, ID: {result_id}"
                )
            else:
                logger.warning(
                    f"存储 EntitySerialization 失败: {entity_serialization.name}"
                )

        logger.info(
            f"批量存储 EntitySerialization 完成，成功: {len(saved_ids)}/{len(entities_serialization)}"
        )
        return saved_ids

    except Exception as e:
        logger.error(f"存储 EntitySerializations 失败: {e}")
        raise


###############################################################################################################################################
def _save_entity_components(
    entity_serialization: EntitySerialization,
    entity_serialization_id: str,
    world_id: str,
) -> None:
    """
    存储实体的所有组件内容到 MongoDB

    参数:
        entity_serialization: EntitySerialization 对象
        entity_serialization_id: EntitySerialization 文档的 ID
        world_id: World 文档的 ID
    """
    try:
        for idx, component in enumerate(entity_serialization.components):
            # 生成组件 ID
            component_id = f"comp_{world_id}_{entity_serialization.name}_{idx}"

            # 创建组件文档（使用 _id 参数）
            component_doc = EntityComponentDocument(
                _id=component_id,  # 使用 _id 而不是 id
                entity_serialization_id=entity_serialization_id,
                world_id=world_id,
                entity_name=entity_serialization.name,
                component_name=component.name,
                index=idx,
                component_data=component.model_dump_json(),  # 序列化组件内容
            )

            # 存储到 MongoDB
            doc_dict = component_doc.model_dump(by_alias=True)
            mongo_insert_one("entity_components", doc_dict)

            logger.debug(
                f"存储组件成功: {entity_serialization.name}.{component.name}, index={idx}"
            )

    except Exception as e:
        logger.error(f"存储组件失败: {entity_serialization.name}, 错误: {e}")
        raise


###############################################################################################################################################
def load_entity_serializations(world_id: str) -> List[EntitySerialization]:
    """
    从 MongoDB 加载所有 EntitySerialization

    参数:
        world_id: World 文档的 ID

    返回:
        List[EntitySerialization]: EntitySerialization 列表

    说明:
        - 从 entity_serializations 集合加载所有关联到该 world_id 的文档
        - 从 entity_components 集合加载实际组件内容
        - 完整还原 EntitySerialization 对象
    """
    try:
        # 查询所有属于该 world_id 的 EntitySerialization 文档
        entity_docs = mongo_find_many(
            "entity_serializations", filter_dict={"world_id": world_id}
        )

        entities_serialization: List[EntitySerialization] = []

        for doc in entity_docs:
            entity_name = doc["entity_name"]
            entity_serialization_id = doc["_id"]

            # 加载实体的所有组件
            components = _load_entity_components(entity_serialization_id)

            # 创建 EntitySerialization
            entity_serialization = EntitySerialization(
                name=entity_name,
                components=components,
            )
            entities_serialization.append(entity_serialization)

            logger.debug(
                f"加载 EntitySerialization: {entity_name}, "
                f"组件数: {len(components)}"
            )

        logger.info(f"加载 {len(entities_serialization)} 个 EntitySerialization")
        return entities_serialization

    except Exception as e:
        logger.error(f"加载 EntitySerializations 失败: {e}")
        raise


###############################################################################################################################################
def _load_entity_components(
    entity_serialization_id: str,
) -> List[ComponentSerialization]:
    """
    从 MongoDB 加载实体的所有组件

    参数:
        entity_serialization_id: EntitySerialization 文档的 ID

    返回:
        List[ComponentSerialization]: 组件列表
    """
    try:
        # 查询所有属于该实体的组件
        component_docs = mongo_find_many(
            "entity_components",
            filter_dict={"entity_serialization_id": entity_serialization_id},
            sort=[("index", 1)],  # 按 index 排序
        )

        components: List[ComponentSerialization] = []

        for doc in component_docs:
            # 从 JSON 字符串反序列化组件
            component = ComponentSerialization.model_validate_json(
                doc["component_data"]
            )
            components.append(component)

            logger.debug(
                f"加载组件: {doc['entity_name']}.{doc['component_name']}, index={doc['index']}"
            )

        return components

    except Exception as e:
        logger.error(
            f"加载组件失败: entity_serialization_id={entity_serialization_id}, 错误: {e}"
        )
        raise


###############################################################################################################################################
