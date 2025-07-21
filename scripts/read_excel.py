import pandas as pd
import os
from loguru import logger
from pydantic import BaseModel

from multi_agents_game.models import dungeon

def read_excel_file(file_path, sheet_name=None):
    """
    读取Excel文件
    
    Args:
        file_path (str): Excel文件路径
        sheet_name (str, optional): 工作表名称，默认读取第一个工作表
    
    Returns:
        pandas.DataFrame: 读取的数据
    """
    try:
        if not os.path.exists(file_path):
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

def get_sheet_names(file_path):
    """
    获取Excel文件中所有工作表名称
    
    Args:
        file_path (str): Excel文件路径
    
    Returns:
        list: 工作表名称列表
    """
    try:
        excel_file = pd.ExcelFile(file_path)
        return excel_file.sheet_names
    except Exception as e:
        logger.error(f"获取工作表名称时出错: {e}")
        return []

def get_value(df, row, col):
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

def get_dungeon_info(file_path, sheet_name, row):
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

def get_actor_info(file_path, sheet_name, row):
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
    

class DungeonInfo(BaseModel):
    name: str
    character_sheet_name: str
    dungeon_name: str
    stage_profile: str
    actor: str

def display_excel_info(df):
    """
    显示Excel数据基本信息
    
    Args:
        df (pandas.DataFrame): 要显示信息的数据框
    """
    if df is None:
        logger.warning("数据为空")
        return
    
    logger.info("\n=== Excel数据基本信息 ===")
    logger.info(f"行数: {df.shape[0]}")
    logger.info(f"列数: {df.shape[1]}")
    logger.info(f"列名: {list(df.columns)}")
    
    logger.info("\n=== 前5行数据 ===")
    logger.info(f"\n{df.head()}")
    
    logger.info("\n=== 数据类型 ===")
    logger.info(f"\n{df.dtypes}")
    
    logger.info("\n=== 缺失值统计 ===")
    logger.info(f"\n{df.isnull().sum()}")


def main():
    """
    主函数，用于测试
    """
    # 示例用法
    file_path = "读表测试.xlsx"  # 替换为你的Excel文件路径
    sheet_name = "dungeons"  
    sheet_name2 = "actors"     # 替换为你的工作表名称
                    # 行索引（从0开始）
    
    # 测试读取dungeon信息
    dungeon_info = get_dungeon_info(file_path, sheet_name, 2)
    if dungeon_info:
        logger.info("=== Dungeon Info ===")
        for key, value in dungeon_info.items():
            logger.info(f"{key}: {type(value)} = {value}")

    # 测试读取actor信息
    actor_info = get_actor_info(file_path, sheet_name2, 0)
    if actor_info:
        logger.info("\n=== Actor Info ===")
        for key, value in actor_info.items():
            logger.info(f"{key}: {type(value)} = {value}")


if __name__ == "__main__":
    main()