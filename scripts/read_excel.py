import pandas as pd
from typing import Optional, List, Dict, Any
from loguru import logger
from pathlib import Path


#####################################################################################################
#####################################################################################################
#####################################################################################################
def read_excel_file(
    file_path: str, sheet_name: Optional[str] = None
) -> Optional[pd.DataFrame]:
    """
    读取Excel文件

    Args:
        file_path (str): Excel文件路径
        sheet_name (str, optional): 工作表名称，默认读取第一个工作表

    Returns:
        pandas.DataFrame: 读取的数据
    """
    try:
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            logger.error(f"文件不存在: {file_path}")
            return None

        # 读取Excel文件
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            logger.info(f"成功读取工作表 '{sheet_name}' 从文件: {file_path}")
        else:
            df = pd.read_excel(file_path)
            logger.info(f"成功读取文件: {file_path}")

        logger.info(f"数据形状: {df.shape}")
        return df

    except Exception as e:
        logger.error(f"读取Excel文件时出错: {e}")
        return None


#####################################################################################################
#####################################################################################################
#####################################################################################################
def get_value(df: pd.DataFrame, row: int, col: str) -> Any:
    """
    通过行索引和列名获取单元格值

    Args:
        df (pandas.DataFrame): 数据框
        row (int): 行索引（从0开始）
        col (str): 列名

    Returns:
        单元格的值
    """
    try:
        value = df.loc[row, col]
        logger.debug(f"第{row+1}行，列'{col}'的值: {value}")
        return value
    except Exception as e:
        logger.error(f"获取值时出错: {e}")
        return None


#####################################################################################################
#####################################################################################################
#####################################################################################################
def get_dungeon_info(
    file_path: str, sheet_name: str, row: int
) -> Optional[Dict[str, Any]]:
    """
    从指定工作表读取特定行列的值

    Args:
        file_path (str): Excel文件路径
        sheet_name (str): 工作表名称
        row (int): 行索引（从0开始）
        column (str): 列名
        default_value: 默认值

    Returns:
        单元格的值或默认值
    """

    # 读取指定工作表
    df = read_excel_file(file_path, sheet_name)
    if df is None:
        logger.warning(f"无法读取工作表 '{sheet_name}'")
        return None

    try:
        dungeon_info = {
            "name": get_value(df, row, "name"),
            "character_sheet_name": get_value(df, row, "character_sheet_name"),
            "dungeon_name": get_value(df, row, "dungeon_name"),
            "stage_profile": get_value(df, row, "stage_profile"),
            "actor": get_value(df, row, "actor"),
        }
        return dungeon_info
    except Exception as e:
        logger.error(f"从工作表 '{sheet_name}' 获取值时出错: {e}")
        return None


#####################################################################################################
#####################################################################################################
#####################################################################################################
def get_actor_info(
    file_path: str, sheet_name: str, row: int
) -> Optional[Dict[str, Any]]:
    df = read_excel_file(file_path, sheet_name)
    if df is None:
        logger.warning(f"无法读取工作表 '{sheet_name}'")
        return None

    try:
        actor_info = {
            "name": get_value(df, row, "name"),
            "character_sheet_name": get_value(df, row, "character_sheet_name"),
            "type": get_value(df, row, "type"),
            "actor_profile": get_value(df, row, "actor_profile"),
            "appearance": get_value(df, row, "appearance"),
            "kick_off_message": get_value(df, row, "kick_off_message"),
        }
        return actor_info

    except Exception as e:
        logger.error(f"从工作表 '{sheet_name}' 获取值时出错: {e}")
        return None


#####################################################################################################
#####################################################################################################
#####################################################################################################
def list_valid_rows(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    列举所有有效行数据（过滤掉第一个元素为NaN或空字符串的行）

    Args:
        df (pandas.DataFrame): 要列举的数据框

    Returns:
        list: 有效行数据的列表
    """
    if df.empty:
        logger.warning("数据为空")
        return []

    valid_rows = []
    first_column = df.columns[0]  # 获取第一列的列名

    logger.info(f"\n=== 列举有效行数据 (过滤第一列 '{first_column}' 为空的行) ===")

    for index, row in df.iterrows():
        first_value = row.iloc[0]  # 获取第一个元素
        row_number = int(index) if isinstance(index, (int, float)) else 0

        # 检查第一个元素是否为NaN或空字符串
        if pd.isna(first_value) or (
            isinstance(first_value, str) and first_value.strip() == ""
        ):
            logger.debug(f"跳过第 {row_number + 1} 行: 第一个元素为空 ({first_value})")
            continue

        # 记录有效行
        row_dict = row.to_dict()
        valid_rows.append(row_dict)

        logger.info(f"\n第 {row_number + 1} 行 (索引 {index}) - 有效:")
        for col_name, value in row_dict.items():
            logger.info(f"  {col_name}: {type(value).__name__} = {value}")
        logger.info("-" * 50)

    logger.info(f"\n总计找到 {len(valid_rows)} 行有效数据")
    return valid_rows


#####################################################################################################
#####################################################################################################
#####################################################################################################
def get_column_names(file_path: str, sheet_name: str) -> Optional[List[str]]:
    """
    获取指定工作表的列名（表头/第一行）

    Args:
        file_path (str): Excel文件路径
        sheet_name (str): 工作表名称

    Returns:
        List[str]: 列名列表，如果获取失败返回None
    """
    # 读取指定工作表
    df = read_excel_file(file_path, sheet_name)
    if df is None:
        logger.warning(f"无法读取工作表 '{sheet_name}'")
        return None

    if df.empty:
        logger.warning("工作表为空")
        return None

    try:
        # 获取所有列名
        column_names = df.columns.tolist()

        logger.info("\n=== 表格列名（第一行/表头）===")
        logger.info("-" * 40)

        for i, col_name in enumerate(column_names, 1):
            logger.info(f"{i:2d}. {col_name}")

        logger.info("-" * 40)
        logger.info(f"总共有 {len(column_names)} 个列")

        # 格式化输出你需要的key格式
        logger.info("\n=== 格式化的Key列表 ===")
        for col_name in column_names:
            logger.info(f"{col_name}: ")

        return column_names

    except Exception as e:
        logger.error(f"获取列名时出错: {e}")
        return None


#####################################################################################################
#####################################################################################################
#####################################################################################################
def display_excel_info(df: pd.DataFrame, sheet_name: str = "") -> None:
    """
    显示Excel数据基本信息

    Args:
        df (pandas.DataFrame): 要显示信息的数据框
        sheet_name (str): 工作表名称，用于显示标题
    """
    if df.empty:
        logger.warning("数据为空")
        return

    title = f"Excel数据基本信息 - {sheet_name}" if sheet_name else "Excel数据基本信息"
    logger.info(f"\n=== {title} ===")
    logger.info(f"行数: {df.shape[0]}")
    logger.info(f"列数: {df.shape[1]}")
    logger.info(f"列名: {list(df.columns)}")

    logger.info("\n=== 前5行数据预览 ===")
    # 使用更好的格式显示数据
    logger.info("\n" + df.head().to_string())

    logger.info("\n=== 数据类型 ===")
    for col_name, dtype in df.dtypes.items():
        logger.info(f"{col_name:<25}: {dtype}")

    logger.info("\n=== 缺失值统计 ===")
    null_counts = df.isnull().sum()
    total_rows = len(df)

    for col_name, null_count in null_counts.items():
        percentage = (null_count / total_rows * 100) if total_rows > 0 else 0
        logger.info(f"{col_name:<25}: {null_count:>3d} ({percentage:>5.1f}%)")

    logger.info(f"\n总计: {total_rows} 行数据")
    logger.info("=" * 60)


#####################################################################################################
#####################################################################################################
#####################################################################################################
def analyze_dungeons_sheet(file_path: str, sheet_name: str) -> None:
    """
    分析dungeons工作表

    Args:
        file_path (str): Excel文件路径
        sheet_name (str): 工作表名称
    """
    logger.info("\n" + "=" * 60)
    logger.info("📊 分析 'dungeons' 工作表")
    logger.info("=" * 60)

    df_dungeons = read_excel_file(file_path, sheet_name)
    if df_dungeons is None:
        logger.error("❌ 无法读取 'dungeons' 工作表")
        return

    # 显示基本信息
    display_excel_info(df_dungeons, sheet_name)

    # 测试列举有效行数据
    valid_rows = list_valid_rows(df_dungeons)
    logger.info(f"\n=== 有效行数据总结 ===")
    logger.info(f"总共找到 {len(valid_rows)} 行有效数据")
    logger.info(f"{valid_rows}")

    # 测试获取列名（表头）
    _test_get_column_names(file_path, sheet_name)

    # 测试读取特定dungeon信息
    _test_get_dungeon_info(file_path, sheet_name)


#####################################################################################################
#####################################################################################################
#####################################################################################################
def analyze_actors_sheet(file_path: str, sheet_name: str) -> None:
    """
    分析actors工作表

    Args:
        file_path (str): Excel文件路径
        sheet_name (str): 工作表名称
    """
    logger.info("\n" + "=" * 60)
    logger.info("👹 分析 'actors' 工作表")
    logger.info("=" * 60)

    df_actors = read_excel_file(file_path, sheet_name)
    if df_actors is None:
        logger.error("❌ 无法读取 'actors' 工作表")
        return

    # 显示基本信息
    display_excel_info(df_actors, sheet_name)

    # 测试读取actor信息
    _test_get_actor_info(file_path, sheet_name)


#####################################################################################################
#####################################################################################################
#####################################################################################################
def _test_get_column_names(file_path: str, sheet_name: str) -> None:
    """测试获取列名功能"""
    logger.info("\n" + "=" * 50)
    logger.info("📋 获取列名（表头）")
    logger.info("=" * 50)

    column_names = get_column_names(file_path, sheet_name)
    if column_names:
        logger.info("✅ 成功获取列名")
    else:
        logger.warning("❌ 获取列名失败")


#####################################################################################################
#####################################################################################################
#####################################################################################################


def _test_get_dungeon_info(file_path: str, sheet_name: str) -> None:
    """测试获取dungeon信息功能"""
    logger.info("\n" + "=" * 50)
    logger.info("🏰 测试读取特定dungeon信息 (第3行)")
    logger.info("=" * 50)

    dungeon_info = get_dungeon_info(file_path, sheet_name, 2)
    if dungeon_info:
        logger.info("=== Dungeon Info ===")
        for key, value in dungeon_info.items():
            logger.info(f"{key}: {type(value)} = {value}")
        name = dungeon_info["name"]
        logger.info(f"{type(name)}: {name}")
    else:
        logger.warning("❌ 获取dungeon信息失败")


#####################################################################################################
#####################################################################################################
#####################################################################################################


def _test_get_actor_info(file_path: str, sheet_name: str) -> None:
    """测试获取actor信息功能"""
    logger.info("\n" + "=" * 50)
    logger.info("🎭 测试读取actor信息 (第1行)")
    logger.info("=" * 50)

    actor_info = get_actor_info(file_path, sheet_name, 0)
    if actor_info:
        logger.info("\n=== Actor Info ===")
        for key, value in actor_info.items():
            logger.info(f"{key}: {type(value)} = {value}")
    else:
        logger.warning("❌ 获取actor信息失败")


#####################################################################################################
#####################################################################################################
#####################################################################################################


def main() -> None:
    """
    主函数，用于测试Excel读取功能
    """
    # 配置文件路径和工作表名称
    file_path = "读表测试.xlsx"
    dungeons_sheet = "dungeons"
    actors_sheet = "actors"

    # 开始分析
    logger.info("🚀 开始Excel文件分析...")

    # 分析dungeons工作表
    analyze_dungeons_sheet(file_path, dungeons_sheet)

    # 分析actors工作表
    analyze_actors_sheet(file_path, actors_sheet)

    # 完成分析
    logger.info("\n🎉 Excel文件分析完成！")


#####################################################################################################
#####################################################################################################
#####################################################################################################

if __name__ == "__main__":
    main()
