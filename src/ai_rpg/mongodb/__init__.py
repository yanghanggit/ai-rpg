"""
MongoDB 模块

包含 MongoDB 相关的配置、客户端操作、文档模型等功能
"""

from .boot_document import BootDocument
from .client import (
    MongoClientType,
    MongoCollectionType,
    MongoDatabaseType,
    MongoDocumentType,
    MongoFilterType,
    MongoSortType,
    MongoUpdateType,
    get_mongodb_client,
    get_mongodb_client_instance,
    get_mongodb_database,
    get_mongodb_database_instance,
    mongodb_clear_collection,
    mongodb_clear_database,
    mongodb_close_connection,
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
)
from .config import DEFAULT_MONGODB_CONFIG, MongoDBConfig
from .world_document import WorldDocument

__all__ = [
    # 配置
    "MongoDBConfig",
    "DEFAULT_MONGODB_CONFIG",
    # 文档模型
    "BootDocument",
    "WorldDocument",
    # 客户端类型
    "MongoClientType",
    "MongoDatabaseType",
    "MongoCollectionType",
    "MongoDocumentType",
    "MongoFilterType",
    "MongoUpdateType",
    "MongoSortType",
    # 客户端连接函数
    "get_mongodb_client",
    "get_mongodb_database",
    "get_mongodb_client_instance",
    "get_mongodb_database_instance",
    "mongodb_close_connection",
    # 数据库操作函数
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
]
