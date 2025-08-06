from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    TypeAlias,
    cast,
)

import pymongo
from loguru import logger
from pymongo.errors import PyMongoError

from ..config import MongoDBConfig

# MongoDB文档类型 - 可以是字典或继承自BaseMongoDocument的类型
MongoDocumentType: TypeAlias = Dict[str, Any]
MongoFilterType: TypeAlias = Dict[str, Any]
MongoUpdateType: TypeAlias = Dict[str, Any]
MongoSortType: TypeAlias = List[tuple[str, int]]

# 为MongoDB客户端定义明确的类型
if TYPE_CHECKING:
    from pymongo import MongoClient
    from pymongo.collection import Collection
    from pymongo.database import Database

    MongoClientType: TypeAlias = "MongoClient[MongoDocumentType]"
    MongoDatabaseType: TypeAlias = "Database[MongoDocumentType]"
    MongoCollectionType: TypeAlias = "Collection[MongoDocumentType]"
else:
    MongoClientType: TypeAlias = pymongo.MongoClient  # type: ignore[type-arg]
    MongoDatabaseType: TypeAlias = pymongo.database.Database  # type: ignore[type-arg]
    MongoCollectionType: TypeAlias = pymongo.collection.Collection  # type: ignore[type-arg]


###################################################################################################
def get_mongodb_client() -> MongoClientType:
    """
    获取MongoDB连接实例。

    返回:
        MongoClientType: MongoDB客户端实例
    """
    mongodb_config = MongoDBConfig()
    client = cast(
        MongoClientType, pymongo.MongoClient(mongodb_config.connection_string)
    )

    # 测试连接
    try:
        client.admin.command("ping")
        logger.info("MongoDB连接成功")
    except Exception as e:
        logger.error(f"MongoDB连接失败: {e}")
        raise e

    return client


###################################################################################################
def get_mongodb_database() -> MongoDatabaseType:
    """
    获取MongoDB数据库实例。

    返回:
        MongoDatabaseType: MongoDB数据库实例
    """
    mongodb_config = MongoDBConfig()
    client = get_mongodb_client()
    return client[mongodb_config.database]


###################################################################################################
# 获取MongoDB客户端的单例实例
_mongodb_client_instance: Optional[MongoClientType] = None
_mongodb_database_instance: Optional[MongoDatabaseType] = None


###################################################################################################
def get_mongodb_client_instance() -> MongoClientType:
    """
    获取MongoDB客户端单例实例。

    返回:
        MongoClientType: MongoDB客户端实例
    """
    global _mongodb_client_instance
    if _mongodb_client_instance is None:
        _mongodb_client_instance = get_mongodb_client()
    return _mongodb_client_instance


###################################################################################################
def get_mongodb_database_instance() -> MongoDatabaseType:
    """
    获取MongoDB数据库单例实例。

    返回:
        MongoDatabaseType: MongoDB数据库实例
    """
    global _mongodb_database_instance
    if _mongodb_database_instance is None:
        _mongodb_database_instance = get_mongodb_database()
    return _mongodb_database_instance


###################################################################################################
def mongodb_insert_one(
    collection_name: str, document: MongoDocumentType
) -> Optional[str]:
    """
    向MongoDB集合中插入一个文档。

    参数:
        collection_name: 集合名称
        document: 要插入的文档

    返回:
        Optional[str]: 插入的文档ID，失败时返回None

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collection = db[collection_name]
        result = collection.insert_one(document)
        logger.debug(
            f"MongoDB插入文档成功，集合: {collection_name}, ID: {result.inserted_id}"
        )
        return str(result.inserted_id)
    except PyMongoError as e:
        logger.error(f"MongoDB插入文档失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_insert_many(
    collection_name: str, documents: List[MongoDocumentType]
) -> List[str]:
    """
    向MongoDB集合中插入多个文档。

    参数:
        collection_name: 集合名称
        documents: 要插入的文档列表

    返回:
        List[str]: 插入的文档ID列表

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collection = db[collection_name]
        result = collection.insert_many(documents)
        logger.debug(
            f"MongoDB批量插入文档成功，集合: {collection_name}, 数量: {len(result.inserted_ids)}"
        )
        return [str(obj_id) for obj_id in result.inserted_ids]
    except PyMongoError as e:
        logger.error(f"MongoDB批量插入文档失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_find_one(
    collection_name: str, filter_dict: Optional[MongoFilterType] = None
) -> Optional[MongoDocumentType]:
    """
    从MongoDB集合中查找一个文档。

    参数:
        collection_name: 集合名称
        filter_dict: 查询过滤条件

    返回:
        Optional[MongoDocumentType]: 查找到的文档，未找到时返回None

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collection = db[collection_name]
        result = collection.find_one(filter_dict or {})
        logger.debug(
            f"MongoDB查找文档，集合: {collection_name}, 找到: {result is not None}"
        )
        return result
    except PyMongoError as e:
        logger.error(f"MongoDB查找文档失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_find_many(
    collection_name: str,
    filter_dict: Optional[MongoFilterType] = None,
    sort: Optional[MongoSortType] = None,
    limit: Optional[int] = None,
    skip: Optional[int] = None,
) -> List[MongoDocumentType]:
    """
    从MongoDB集合中查找多个文档。

    参数:
        collection_name: 集合名称
        filter_dict: 查询过滤条件
        sort: 排序条件
        limit: 限制返回数量
        skip: 跳过文档数量

    返回:
        List[MongoDocumentType]: 查找到的文档列表

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collection = db[collection_name]
        cursor = collection.find(filter_dict or {})

        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)

        result = list(cursor)
        logger.debug(
            f"MongoDB查找多个文档，集合: {collection_name}, 数量: {len(result)}"
        )
        return result
    except PyMongoError as e:
        logger.error(f"MongoDB查找多个文档失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_upsert_one(
    collection_name: str, document: MongoDocumentType, filter_key: str = "_id"
) -> Optional[str]:
    """
    插入或替换MongoDB文档（如果存在则完全覆盖）。

    这是一个便捷方法，基于指定的键进行查找和替换。
    适用于需要"完全覆盖"语义的场景。

    参数:
        collection_name: 集合名称
        document: 要插入或替换的完整文档
        filter_key: 用于查找现有文档的键名，默认为 "_id"

    返回:
        Optional[str]: 文档ID，失败时返回None

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        if filter_key not in document:
            raise ValueError(f"文档中缺少过滤键: {filter_key}")

        # 构建过滤条件
        filter_dict = {filter_key: document[filter_key]}

        # 使用 replace_one 实现 upsert（完全覆盖）
        return mongodb_replace_one(collection_name, filter_dict, document, upsert=True)

    except PyMongoError as e:
        logger.error(f"MongoDB upsert 操作失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_replace_one(
    collection_name: str,
    filter_dict: MongoFilterType,
    document: MongoDocumentType,
    upsert: bool = True,
) -> Optional[str]:
    """
    替换MongoDB集合中的一个文档（完全覆盖）。

    参数:
        collection_name: 集合名称
        filter_dict: 查询过滤条件
        document: 要替换的完整文档
        upsert: 如果文档不存在是否插入，默认为True

    返回:
        Optional[str]: 文档ID（新插入或被替换的文档ID），失败时返回None

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collection = db[collection_name]
        result = collection.replace_one(filter_dict, document, upsert=upsert)

        if result.upserted_id:
            # 新插入的文档
            logger.debug(
                f"MongoDB插入新文档，集合: {collection_name}, ID: {result.upserted_id}"
            )
            return str(result.upserted_id)
        elif result.modified_count > 0:
            # 替换了现有文档
            document_id = document.get("_id", "unknown")
            logger.debug(f"MongoDB替换文档，集合: {collection_name}, ID: {document_id}")
            return str(document_id)
        else:
            # 没有匹配的文档且 upsert=False
            logger.warning(f"MongoDB替换操作未影响任何文档，集合: {collection_name}")
            return None

    except PyMongoError as e:
        logger.error(f"MongoDB替换文档失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_update_one(
    collection_name: str,
    filter_dict: MongoFilterType,
    update_dict: MongoUpdateType,
    upsert: bool = False,
) -> bool:
    """
    更新MongoDB集合中的一个文档。

    参数:
        collection_name: 集合名称
        filter_dict: 查询过滤条件
        update_dict: 更新操作
        upsert: 如果文档不存在是否插入

    返回:
        bool: 是否成功更新了文档

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collection = db[collection_name]
        result = collection.update_one(filter_dict, update_dict, upsert=upsert)
        success = result.modified_count > 0 or (
            upsert and result.upserted_id is not None
        )
        logger.debug(
            f"MongoDB更新文档，集合: {collection_name}, 成功: {success}, 修改数量: {result.modified_count}"
        )
        return success
    except PyMongoError as e:
        logger.error(f"MongoDB更新文档失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_update_many(
    collection_name: str,
    filter_dict: MongoFilterType,
    update_dict: MongoUpdateType,
    upsert: bool = False,
) -> int:
    """
    更新MongoDB集合中的多个文档。

    参数:
        collection_name: 集合名称
        filter_dict: 查询过滤条件
        update_dict: 更新操作
        upsert: 如果文档不存在是否插入

    返回:
        int: 更新的文档数量

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collection = db[collection_name]
        result = collection.update_many(filter_dict, update_dict, upsert=upsert)
        logger.debug(
            f"MongoDB批量更新文档，集合: {collection_name}, 修改数量: {result.modified_count}"
        )
        return result.modified_count
    except PyMongoError as e:
        logger.error(f"MongoDB批量更新文档失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_delete_one(collection_name: str, filter_dict: MongoFilterType) -> bool:
    """
    从MongoDB集合中删除一个文档。

    参数:
        collection_name: 集合名称
        filter_dict: 查询过滤条件

    返回:
        bool: 是否成功删除了文档

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collection = db[collection_name]
        result = collection.delete_one(filter_dict)
        success = result.deleted_count > 0
        logger.debug(f"MongoDB删除文档，集合: {collection_name}, 成功: {success}")
        return success
    except PyMongoError as e:
        logger.error(f"MongoDB删除文档失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_delete_many(collection_name: str, filter_dict: MongoFilterType) -> int:
    """
    从MongoDB集合中删除多个文档。

    参数:
        collection_name: 集合名称
        filter_dict: 查询过滤条件

    返回:
        int: 删除的文档数量

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collection = db[collection_name]
        result = collection.delete_many(filter_dict)
        logger.debug(
            f"MongoDB批量删除文档，集合: {collection_name}, 删除数量: {result.deleted_count}"
        )
        return result.deleted_count
    except PyMongoError as e:
        logger.error(f"MongoDB批量删除文档失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_count_documents(
    collection_name: str, filter_dict: Optional[MongoFilterType] = None
) -> int:
    """
    统计MongoDB集合中的文档数量。

    参数:
        collection_name: 集合名称
        filter_dict: 查询过滤条件

    返回:
        int: 文档数量

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collection = db[collection_name]
        count = collection.count_documents(filter_dict or {})
        logger.debug(f"MongoDB统计文档数量，集合: {collection_name}, 数量: {count}")
        return count
    except PyMongoError as e:
        logger.error(f"MongoDB统计文档数量失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_create_index(
    collection_name: str, index_keys: List[tuple[str, int]], unique: bool = False
) -> str:
    """
    为MongoDB集合创建索引。

    参数:
        collection_name: 集合名称
        index_keys: 索引键列表，格式为[(字段名, 排序方向)]
        unique: 是否为唯一索引

    返回:
        str: 索引名称

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collection = db[collection_name]
        index_name = collection.create_index(index_keys, unique=unique)
        logger.info(f"MongoDB创建索引成功，集合: {collection_name}, 索引: {index_name}")
        return index_name
    except PyMongoError as e:
        logger.error(f"MongoDB创建索引失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_list_collections() -> List[str]:
    """
    列出MongoDB数据库中的所有集合。

    返回:
        List[str]: 集合名称列表

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collections = db.list_collection_names()
        logger.debug(f"MongoDB列出集合，数量: {len(collections)}")
        return collections
    except PyMongoError as e:
        logger.error(f"MongoDB列出集合失败，错误: {e}")
        raise e


###################################################################################################
def mongodb_drop_collection(collection_name: str) -> None:
    """
    删除MongoDB集合。

    参数:
        collection_name: 集合名称

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        db.drop_collection(collection_name)
        logger.warning(f"MongoDB删除集合: {collection_name}")
    except PyMongoError as e:
        logger.error(f"MongoDB删除集合失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_clear_database() -> None:
    """
    清空MongoDB数据库中的所有集合（危险操作）。

    注意：这是一个危险操作，会删除数据库中的所有集合和数据！
    请在使用前确认操作的必要性。

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collections = db.list_collection_names()

        # 删除所有集合
        for collection_name in collections:
            db.drop_collection(collection_name)
            logger.warning(f"已删除集合: {collection_name}")

        logger.warning(f"MongoDB数据库清空完成，共删除 {len(collections)} 个集合")
    except PyMongoError as e:
        logger.error(f"MongoDB清空数据库失败，错误: {e}")
        raise e


###################################################################################################
def mongodb_clear_collection(collection_name: str) -> int:
    """
    清空MongoDB集合中的所有文档（保留集合结构和索引）。

    参数:
        collection_name: 集合名称

    返回:
        int: 删除的文档数量

    抛出:
        PyMongoError: 当MongoDB操作失败时
    """
    try:
        db = get_mongodb_database_instance()
        collection = db[collection_name]
        result = collection.delete_many({})  # 空条件匹配所有文档
        logger.warning(
            f"MongoDB清空集合: {collection_name}, 删除文档数量: {result.deleted_count}"
        )
        return result.deleted_count
    except PyMongoError as e:
        logger.error(f"MongoDB清空集合失败，集合: {collection_name}, 错误: {e}")
        raise e


###################################################################################################
def mongodb_close_connection() -> None:
    """
    关闭MongoDB连接。
    """
    global _mongodb_client_instance, _mongodb_database_instance
    try:
        if _mongodb_client_instance is not None:
            _mongodb_client_instance.close()
            _mongodb_client_instance = None
            _mongodb_database_instance = None
            logger.info("MongoDB连接已关闭")
    except Exception as e:
        logger.error(f"关闭MongoDB连接时出错: {e}")


###################################################################################################
