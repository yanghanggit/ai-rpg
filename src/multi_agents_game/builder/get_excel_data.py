from typing import List, Dict, Any
from loguru import logger
from ..models.excel_data import DungeonExcelData, ActorExcelData
from ..builder.read_excel_utils import (
    read_excel_file,
    list_valid_rows,
    list_valid_rows_as_models,
    safe_get_from_dict,
)

# Excel文件路径
file_path = "excel_test.xlsx"

# 数据缓存 - 使用BaseModel替代Dict[str, Any]
dungeon_valid_rows: List[DungeonExcelData] = []
actor_valid_rows: List[ActorExcelData] = []

# 保留原有的dict格式缓存，用于向后兼容
dungeon_valid_rows_dict: List[Dict[str, Any]] = []
actor_valid_rows_dict: List[Dict[str, Any]] = []


def load_excel_data() -> None:
    """加载Excel数据到全局变量中"""
    global dungeon_valid_rows, actor_valid_rows, dungeon_valid_rows_dict, actor_valid_rows_dict

    #######################################################################################################################################
    #######################################################################################################################################
    # 提取地牢信息
    sheet_name = "dungeons"

    df = read_excel_file(file_path, sheet_name)
    if df is None:
        logger.error("无法读取Excel文件")
        dungeon_valid_rows = []
        dungeon_valid_rows_dict = []
    else:
        # 使用新的BaseModel方式
        dungeon_valid_rows = list_valid_rows_as_models(df, "dungeon")
        # 保留原有字典格式，用于向后兼容
        dungeon_valid_rows_dict = list_valid_rows(df)
        if not dungeon_valid_rows:
            logger.warning("没有找到有效数据行")

    #######################################################################################################################################
    #######################################################################################################################################
    # 提取角色信息
    sheet_name = "actors"

    df = read_excel_file(file_path, sheet_name)
    if df is None:
        logger.error("无法读取Excel文件")
        actor_valid_rows = []
        actor_valid_rows_dict = []
    else:
        # 使用新的BaseModel方式
        actor_valid_rows = list_valid_rows_as_models(df, "actor")
        # 保留原有字典格式，用于向后兼容
        actor_valid_rows_dict = list_valid_rows(df)
        if not actor_valid_rows:
            logger.warning("没有找到有效数据行")


# 在模块导入时加载数据
load_excel_data()
