"""
MongoDB 模块

包含 MongoDB 相关的配置、客户端操作、文档模型等功能
"""

from .world_document import WorldDocument
from .boot_document import BootDocument
from .dungeon_document import DungeonDocument
from .client import (
    MongoClientType,
    MongoCollectionType,
    MongoDatabaseType,
    MongoDocumentType,
    MongoFilterType,
    MongoSortType,
    MongoUpdateType,
    mongodb_clear_collection,
    mongodb_clear_database,
    mongodb_count_documents,
    mongodb_create_index,
    mongodb_delete_many,
    mongodb_delete_one,
    mongodb_drop_collection,
    mongodb_find_many,
    mongodb_find_one,
    mongodb_insert_many,
    mongodb_insert_one,
    mongodb_list_collections,
    mongodb_replace_one,
    mongodb_update_many,
    mongodb_update_one,
    mongodb_upsert_one,
    mongodb_client,
    mongodb_database,
)


__all__ = [
    "BootDocument",
    "DungeonDocument",
    "WorldDocument",
    "MongoClientType",
    "MongoDatabaseType",
    "MongoCollectionType",
    "MongoDocumentType",
    "MongoFilterType",
    "MongoUpdateType",
    "MongoSortType",
    "mongodb_insert_one",
    "mongodb_insert_many",
    "mongodb_find_one",
    "mongodb_find_many",
    "mongodb_upsert_one",
    "mongodb_replace_one",
    "mongodb_update_one",
    "mongodb_update_many",
    "mongodb_delete_one",
    "mongodb_delete_many",
    "mongodb_count_documents",
    "mongodb_create_index",
    "mongodb_list_collections",
    "mongodb_drop_collection",
    "mongodb_clear_collection",
    "mongodb_clear_database",
    "mongodb_client",
    "mongodb_database",
]
