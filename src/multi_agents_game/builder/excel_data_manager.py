from typing import List, Dict, Any, Type, TypeVar
from loguru import logger
from .excel_data import DungeonExcelData, ActorExcelData
from .read_excel_utils import (
    read_excel_file,
    list_valid_rows,
    list_valid_rows_as_models,
)

# 定义泛型类型变量
ExcelDataT = TypeVar("ExcelDataT", DungeonExcelData, ActorExcelData)

# Excel文件路径
file_path = "excel_test.xlsx"

# 数据缓存 - 使用BaseModel替代Dict[str, Any]
dungeon_valid_rows: List[DungeonExcelData] = []
actor_valid_rows: List[ActorExcelData] = []

# 保留原有的dict格式缓存，用于向后兼容
dungeon_valid_rows_dict: List[Dict[str, Any]] = []
actor_valid_rows_dict: List[Dict[str, Any]] = []


def load_sheet_data(
    sheet_name: str, model_class: Type[ExcelDataT]
) -> tuple[List[ExcelDataT], List[Dict[str, Any]]]:
    """
    通用的工作表数据加载函数

    Args:
        sheet_name: 工作表名称
        model_class: 要转换到的BaseModel类

    Returns:
        tuple: (BaseModel列表, 字典列表)
    """
    df = read_excel_file(file_path, sheet_name)
    if df is None:
        logger.error(f"无法读取Excel文件中的 '{sheet_name}' 工作表")
        return [], []

    # 使用新的泛型BaseModel方式
    model_rows = list_valid_rows_as_models(df, model_class)
    # 保留原有字典格式，用于向后兼容
    dict_rows = list_valid_rows(df)

    if not model_rows:
        logger.warning(f"在 '{sheet_name}' 工作表中没有找到有效数据行")

    return model_rows, dict_rows


def load_excel_data() -> None:
    """加载Excel数据到全局变量中"""
    global dungeon_valid_rows, actor_valid_rows, dungeon_valid_rows_dict, actor_valid_rows_dict

    # 提取地牢信息
    dungeon_valid_rows, dungeon_valid_rows_dict = load_sheet_data(
        "dungeons", DungeonExcelData
    )

    # 提取角色信息
    actor_valid_rows, actor_valid_rows_dict = load_sheet_data("actors", ActorExcelData)


# 在模块导入时加载数据
load_excel_data()
