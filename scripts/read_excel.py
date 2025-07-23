import pandas as pd
import sys
from pathlib import Path
from typing import Optional
from loguru import logger

# 添加模型导入路径
sys.path.append(str(Path(__file__).parent.parent / "src"))
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
def read_dungeon_data_from_excel(file_path: str, sheet_name: str, row_index: int) -> tuple[str, str, str]:
    """
    从Excel读取地牢数据，只负责读取表格的值

    Args:
        file_path (str): Excel文件路径
        sheet_name (str): 工作表名称
        row_index (int): 行索引（从0开始）

    Returns:
        tuple: (name, character_sheet_name, stage_profile) 三个字符串值的元组
        
    Raises:
        ValueError: 如果读取失败
    """
    try:
        logger.info(f"\n=== 从Excel读取地牢数据 (第{row_index+1}行) ===")
        
        # 读取Excel文件
        df = read_excel_file(file_path, sheet_name)
        if df is None:
            logger.error("无法读取Excel文件")
            raise ValueError("读取Excel文件失败")
        
        # 安全提取单元格值的函数
        def safe_extract(df: pd.DataFrame, row: int, col: str, default: str = "") -> str:
            """安全地从DataFrame提取值"""
            try:
                value = df.loc[row, col]
                if pd.isna(value):
                    return default
                return str(value)
            except (KeyError, IndexError):
                logger.warning(f"列 '{col}' 或行 {row} 不存在，使用默认值")
                return default
        
        # 直接提取各个字段
        name = safe_extract(df, row_index, "name", "未命名地牢")
        character_sheet_name = safe_extract(df, row_index, "character_sheet_name", "default_dungeon")
        stage_profile = safe_extract(df, row_index, "stage_profile", "默认地牢描述：一个神秘的地牢，等待冒险者探索。")
        
        logger.info(f"📋 读取到的地牢数据:")
        logger.info(f"  名称: {name}")
        logger.info(f"  角色表: {character_sheet_name}")
        logger.info(f"  描述: {stage_profile}")
        
        return name, character_sheet_name, stage_profile
        
    except Exception as e:
        logger.error(f"❌ 读取地牢数据失败: {e}")
        raise ValueError(f"读取地牢数据失败: {e}")


def create_dungeon_stage(name: str, character_sheet_name: str, stage_profile: str) -> Optional[Stage]:
    """
    根据地牢数据创建地牢Stage

    Args:
        name (str): 地牢名称
        character_sheet_name (str): 角色表名称
        stage_profile (str): 场景描述

    Returns:
        Stage: 创建的Stage对象，如果失败则返回None
    """
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
        
        logger.info(f"✅ 成功创建地牢Stage: {stage.name}")
        return stage
        
    except Exception as e:
        logger.error(f"❌ 创建地牢Stage失败: {e}")
        return None


def main() -> None:
    """主函数，演示分离的数据读取和地牢创建功能"""
    file_path = "../读表测试.xlsx"  # 修正文件路径
    dungeons_sheet = "dungeons"
    row_index = 2  # 第3行（从0开始）

    logger.info("🚀 开始Excel地牢创建测试...")

    try:
        # 步骤1：读取地牢数据
        logger.info("\n" + "=" * 50)
        logger.info("📖 步骤1：从Excel读取地牢数据")
        logger.info("=" * 50)
        
        name, character_sheet_name, stage_profile = read_dungeon_data_from_excel(file_path, dungeons_sheet, row_index)

        # 步骤2：创建地牢Stage
        logger.info("\n" + "=" * 50)
        logger.info("🏗️ 步骤2：根据数据创建地牢Stage")
        logger.info("=" * 50)
        
        stage = create_dungeon_stage(name, character_sheet_name, stage_profile)
        if stage:
            logger.info(f"✅ 成功创建地牢: {stage.name}")
            logger.info(f"  - 角色表名: {stage.character_sheet.name}")
            logger.info(f"  - 类型: {stage.character_sheet.type}")
            logger.info(f"  - 场景描述: {stage.character_sheet.profile}")
        else:
            logger.error("❌ 创建地牢Stage失败")
            
    except ValueError as e:
        logger.error(f"❌ 数据读取失败: {e}")
        return
    except Exception as e:
        logger.error(f"❌ 程序执行失败: {e}")
        return

    logger.info("\n🎉 地牢创建测试完成！")
    logger.info("\n📝 总结：")
    logger.info("  1. read_dungeon_data_from_excel() - 只负责读取Excel表格数据，返回独立的值")
    logger.info("  2. create_dungeon_stage() - 只负责根据独立参数创建Stage对象")
    logger.info("  3. 功能分离，不使用字典，数据传递更直接")


if __name__ == "__main__":
    main()
