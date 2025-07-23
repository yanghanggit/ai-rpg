import pandas as pd
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from loguru import logger

# 添加模型导入路径
from multi_agents_game.models import StageType, Stage
from multi_agents_game.game.tcg_game_demo_utils import create_stage, CAMPAIGN_SETTING


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
# 这个函数用于显示Excel数据的基本信息，包括行数、列数、列名、前5行数据预览、数据类型和缺失值统计
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


############################################################################################################
##############################################################################################
# 这个函数用于列举所有有效行数据（过滤掉第一个元素为NaN或空字符串的行）
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


############################################################################################################
##############################################################################################
# 这个函数用于安全地从DataFrame提取值，处理可能的异常和缺失值
def safe_extract(df: pd.DataFrame, row: int, col: str, default: str = "") -> str:
    """
    安全地从DataFrame提取值

    Args:
        df (pd.DataFrame): 数据框
        row (int): 行索引
        col (str): 列名
        default (str): 默认值

    Returns:
        str: 提取的值，如果失败则返回默认值
    """
    try:
        value = df.loc[row, col]
        if pd.isna(value):
            return default
        return str(value)
    except (KeyError, IndexError):
        logger.warning(f"列 '{col}' 或行 {row} 不存在，使用默认值")
        return default


############################################################################################################
##############################################################################################
# 这个函数用于安全地从字典获取值，处理可能的NaN值
def safe_get_from_dict(data: Dict[str, Any], key: str, default: str = "") -> str:
    """
    安全获取字典数据，处理NaN值

    Args:
        data (Dict[str, Any]): 数据字典
        key (str): 键名
        default (str): 默认值

    Returns:
        str: 提取的值，如果失败或为NaN则返回默认值
    """
    value = data.get(key, default)
    if pd.isna(value):
        return default
    return str(value)


############################################################################################################
##############################################################################################
# 这个函数用于获取指定工作表的列名（表头/第一行）
def get_column_names(file_path: str, sheet_name: str) -> Optional[List[str]]:
    """
    获取指定工作表的列名（表头/第一行）
    直接从Excel创建地牢Stage，不使用中间函数

    Args:
        file_path (str): Excel文件路径
        sheet_name (str): 工作表名称
        row_index (int): 行索引（从0开始）

    Returns:
        List[str]: 列名列表，如果获取失败返回None
        创建的Stage对象，如果失败则返回None
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


############################################################################################################
##############################################################################################
# 这个函数用于使用list_valid_rows批量创建地牢Stage
def create_dungeons_from_valid_rows(file_path: str, sheet_name: str) -> List[Stage]:
    """
    使用list_valid_rows函数读取数据来批量创建地下城

    Args:
        file_path (str): Excel文件路径
        sheet_name (str): 工作表名称

    Returns:
        List[Stage]: 创建的Stage对象列表
    """
    try:
        logger.info(f"\n=== 使用list_valid_rows批量创建地牢Stage ===")

        # 读取Excel文件
        df = read_excel_file(file_path, sheet_name)
        if df is None:
            logger.error("无法读取Excel文件")
            return []

        # 获取所有有效行数据
        valid_rows = list_valid_rows(df)
        if not valid_rows:
            logger.warning("没有找到有效数据行")
            return []

        stages = []
        logger.info(f"\n🏗️ 开始批量创建地牢Stage，共 {len(valid_rows)} 行有效数据")

        for i, row_data in enumerate(valid_rows):
            logger.info(f"\n--- 处理第 {i+1} 行有效数据 ---")

            # 提取地牢信息
            name = safe_get_from_dict(row_data, "name", "未命名地牢")
            character_sheet_name = safe_get_from_dict(
                row_data, "character_sheet_name", "default_dungeon"
            )
            stage_profile = safe_get_from_dict(
                row_data,
                "stage_profile",
                "默认地牢描述：一个神秘的地牢，等待冒险者探索。",
            )

            logger.info(f"📋 第 {i+1} 行数据:")
            logger.info(f"  名称: {name}")
            logger.info(f"  角色表: {character_sheet_name}")
            logger.info(f"  描述: {stage_profile[:50]}...")  # 只显示前50个字符

            # 直接创建地牢Stage（合并原create_dungeon_stage的逻辑）
            try:
                logger.info(f"\n=== 创建地牢Stage: {name} ===")

                # 创建Stage
                stage = create_stage(
                    name=name,
                    character_sheet_name=character_sheet_name,
                    kick_off_message="",
                    campaign_setting=CAMPAIGN_SETTING,
                    type=StageType.DUNGEON,
                    stage_profile=stage_profile,
                    actors=[],
                )

                stages.append(stage)
                logger.info(f"✅ 成功创建第 {i+1} 个地牢Stage: {stage.name}")

            except Exception as e:
                logger.error(f"❌ 创建第 {i+1} 个地牢Stage失败: {e}")
                continue

        logger.info(f"\n🎉 批量创建完成! 总共成功创建了 {len(stages)} 个地牢Stage")
        return stages

    except Exception as e:
        logger.error(f"❌ 批量创建地牢Stage失败: {e}")
        return []


############################################################################################################
##############################################################################################
# 主函数，演示分离的数据读取和地牢创建功能
def main() -> None:
    """主函数，演示使用list_valid_rows批量创建地牢功能"""
    file_path = "读表测试.xlsx"  # 修正文件路径
    dungeons_sheet = "dungeons"

    logger.info("🚀 开始Excel地牢创建测试...")

    try:
        # 显示Excel基本信息
        logger.info("\n" + "=" * 60)
        logger.info("📊 步骤1：显示Excel数据基本信息")
        logger.info("=" * 60)

        df = read_excel_file(file_path, dungeons_sheet)
        if df is not None:
            display_excel_info(df, dungeons_sheet)
        else:
            logger.error("❌ 无法读取Excel文件")
            return

        # 使用list_valid_rows批量创建地牢
        logger.info("\n" + "=" * 60)
        logger.info("🏭 步骤2：使用list_valid_rows批量创建地牢")
        logger.info("=" * 60)

        stages = create_dungeons_from_valid_rows(file_path, dungeons_sheet)

        if stages:
            logger.info(f"\n📈 批量创建结果总结:")
            for i, stage in enumerate(stages):
                logger.info(
                    f"  {i+1}. {stage.name} (类型: {stage.character_sheet.type})"
                )
                logger.info(f"      角色表: {stage.character_sheet.name}")
                logger.info(f"      描述: {stage.character_sheet.profile[:100]}...")
        else:
            logger.warning("❌ 批量创建失败，没有创建任何地牢")

    except ValueError as e:
        logger.error(f"❌ 数据读取失败: {e}")
        return
    except Exception as e:
        logger.error(f"❌ 程序执行失败: {e}")
        return

    logger.info("\n🎉 地牢创建测试完成！")
    logger.info("\n📝 总结：")
    logger.info("  🎯 统一使用list_valid_rows批量处理策略:")
    logger.info("    • read_excel_file() - 读取Excel文件")
    logger.info("    • display_excel_info() - 显示数据基本信息")
    logger.info("    • list_valid_rows() - 获取所有有效行数据")
    logger.info("    • create_dungeons_from_valid_rows() - 批量创建所有地牢Stage")
    logger.info("  ✅ 功能合并完成，代码结构更加简洁统一")


if __name__ == "__main__":
    main()
