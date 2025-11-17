"""
MongoDB 模块

包含 MongoDB 相关的配置、客户端操作、文档模型等功能
"""

from .world_document import WorldDocument

# from .boot_document import BootDocument
# from .dungeon_document import DungeonDocument
from .client import (
    MongoClientType,
    MongoCollectionType,
    MongoDatabaseType,
    MongoDocumentType,
    MongoFilterType,
    MongoSortType,
    MongoUpdateType,
    mongo_clear_collection,
    mongo_clear_database,
    mongo_count_documents,
    mongo_create_index,
    mongo_delete_many,
    mongo_delete_one,
    mongo_drop_collection,
    mongo_find_many,
    mongo_find_one,
    mongo_insert_many,
    mongo_insert_one,
    mongo_list_collections,
    mongo_replace_one,
    mongo_update_many,
    mongo_update_one,
    mongo_upsert_one,
    mongo_client,
    mongo_database,
)


__all__ = [
    # "BootDocument",
    "DungeonDocument",
    "WorldDocument",
    "MongoClientType",
    "MongoDatabaseType",
    "MongoCollectionType",
    "MongoDocumentType",
    "MongoFilterType",
    "MongoUpdateType",
    "MongoSortType",
    "mongo_insert_one",
    "mongo_insert_many",
    "mongo_find_one",
    "mongo_find_many",
    "mongo_upsert_one",
    "mongo_replace_one",
    "mongo_update_one",
    "mongo_update_many",
    "mongo_delete_one",
    "mongo_delete_many",
    "mongo_count_documents",
    "mongo_create_index",
    "mongo_list_collections",
    "mongo_drop_collection",
    "mongo_clear_collection",
    "mongo_clear_database",
    "mongo_client",
    "mongo_database",
]
