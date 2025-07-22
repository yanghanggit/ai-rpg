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
def create_dungeon_directly_from_excel(file_path: str, sheet_name: str, row_index: int) -> Optional[Stage]:
    """
    直接从Excel创建地牢Stage，不使用中间函数

    Args:
        file_path (str): Excel文件路径
        sheet_name (str): 工作表名称
        row_index (int): 行索引（从0开始）

    Returns:
        创建的Stage对象，如果失败则返回None
    """
    try:
        logger.info(f"\n=== 直接从Excel创建地牢Stage (第{row_index+1}行) ===")
        
        # 直接读取Excel文件
        df = read_excel_file(file_path, sheet_name)
        if df is None:
            logger.error("无法读取Excel文件")
            return None
        
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
        
        # 直接提取所需数据
        name = safe_extract(df, row_index, "name", "未命名地牢")
        character_sheet_name = safe_extract(df, row_index, "character_sheet_name", "default_dungeon")
        stage_profile = safe_extract(df, row_index, "stage_profile", "默认地牢描述：一个神秘的地牢，等待冒险者探索。")
        
        logger.info(f"📋 提取的数据:")
        logger.info(f"  名称: {name}")
        logger.info(f"  角色表: {character_sheet_name}")
        logger.info(f"  描述: {stage_profile}")
        
        # 直接创建Stage
        stage = create_stage(
            name=name,
            character_sheet_name=character_sheet_name,
            kick_off_message="",
            campaign_setting=CAMPAIGN_SETTING,
            type=StageType.DUNGEON,
            stage_profile=stage_profile,
            actors=[],
        )
        
        logger.info(f"✅ 直接创建地牢Stage成功: {stage.name}")
        return stage
        
    except Exception as e:
        logger.error(f"❌ 直接创建地牢Stage失败: {e}")
        return None


def main() -> None:
    """主函数，演示直接从Excel创建地牢Stage"""
    file_path = "../读表测试.xlsx"  # 修正文件路径
    dungeons_sheet = "dungeons"

    logger.info("🚀 开始Excel地牢创建测试...")

    # 使用方法二：直接创建函数
    logger.info("\n" + "=" * 50)
    logger.info("🧪 直接从Excel创建Stage")
    logger.info("=" * 50)
    
    stage_direct = create_dungeon_directly_from_excel(file_path, dungeons_sheet, 2)
    if stage_direct:
        logger.info(f"✅ 成功创建: {stage_direct.name}")
        logger.info(f"  - 角色表名: {stage_direct.character_sheet.name}")
        logger.info(f"  - 类型: {stage_direct.character_sheet.type}")
        logger.info(f"  - 场景描述: {stage_direct.character_sheet.profile}")
    else:
        logger.error("❌ 创建地牢Stage失败")

    logger.info("\n🎉 地牢创建测试完成！")


if __name__ == "__main__":
    main()
