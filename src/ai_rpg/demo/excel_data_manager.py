from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Type, TypeVar, final

from loguru import logger

from ..utils.excel import (
    list_valid_rows,
    list_valid_rows_as_models,
    read_excel_file,
)
from .excel_data import ActorExcelData, DungeonExcelData, WerewolfAppearanceExcelData

# 定义泛型类型变量
ExcelDataT = TypeVar("ExcelDataT", DungeonExcelData, ActorExcelData, WerewolfAppearanceExcelData)


###################################################################################################
###################################################################################################
@final
class ExcelDataManager:
    """Excel数据管理器 - 统一管理Excel文件路径和缓存数据"""

    def __init__(
        self,
        excel_file_path: Path,
        dungeon_sheet_name: Optional[str] = None,
        actor_sheet_name: Optional[str] = None,
        werewolf_appearance_sheet_name: Optional[str] = None,
    ):
        """
        初始化Excel数据管理器

        Args:
            excel_file_path: Excel文件路径
            dungeon_sheet_name: 地牢工作表名称（可选）
            actor_sheet_name: 角色工作表名称（可选）
            werewolf_appearance_sheet_name: 狼人杀外观工作表名称（可选）
        """
        self._excel_file_path: Final[Path] = excel_file_path
        self._dungeon_sheet_name: Optional[str] = dungeon_sheet_name
        self._actor_sheet_name: Optional[str] = actor_sheet_name
        self._werewolf_appearance_sheet_name: Optional[str] = werewolf_appearance_sheet_name

        # BaseModel格式数据缓存
        self._dungeon_valid_rows: List[DungeonExcelData] = []
        self._actor_valid_rows: List[ActorExcelData] = []
        self._werewolf_appearance_valid_rows: List[WerewolfAppearanceExcelData] = []

        # Dict格式数据缓存（向后兼容）
        self._dungeon_valid_rows_dict: List[Dict[str, Any]] = []
        self._actor_valid_rows_dict: List[Dict[str, Any]] = []
        self._werewolf_appearance_valid_rows_dict: List[Dict[str, Any]] = []

        # 直接调用
        self._load_excel_data()

    ###################################################################################################
    def _load_sheet_data(
        self, sheet_name: str, model_class: Type[ExcelDataT]
    ) -> tuple[List[ExcelDataT], List[Dict[str, Any]]]:
        """
        通用的工作表数据加载函数

        Args:
            sheet_name: 工作表名称
            model_class: 要转换到的BaseModel类

        Returns:
            tuple: (BaseModel列表, 字典列表)
        """
        df = read_excel_file(self._excel_file_path, sheet_name)
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

    ###################################################################################################
    def _load_excel_data(self) -> None:
        """加载Excel数据到实例变量中"""
        # logger.info(f"开始从 {self._excel_file_path} 加载Excel数据")

        # 只在指定了工作表名称时才加载对应数据
        if self._dungeon_sheet_name:
            self._dungeon_valid_rows, self._dungeon_valid_rows_dict = self._load_sheet_data(
                self._dungeon_sheet_name, DungeonExcelData
            )

        if self._actor_sheet_name:
            self._actor_valid_rows, self._actor_valid_rows_dict = self._load_sheet_data(
                self._actor_sheet_name, ActorExcelData
            )

        if self._werewolf_appearance_sheet_name:
            (
                self._werewolf_appearance_valid_rows,
                self._werewolf_appearance_valid_rows_dict,
            ) = self._load_sheet_data(
                self._werewolf_appearance_sheet_name, WerewolfAppearanceExcelData
            )

        # logger.info("Excel数据加载完成")

    ###################################################################################################
    def get_dungeon_data(self, name: str) -> Optional[DungeonExcelData]:
        """获取地牢数据"""
        for dungeon in self._dungeon_valid_rows:
            if dungeon.name == name:
                return dungeon
        logger.warning(f"未找到名为 '{name}' 的地牢数据")
        return None

    ###################################################################################################
    def get_actor_data(self, name: str) -> Optional[ActorExcelData]:
        """获取角色数据"""
        for actor in self._actor_valid_rows:
            if actor.name == name:
                return actor
        logger.warning(f"未找到名为 '{name}' 的角色数据")
        return None

    ###################################################################################################
    def get_all_werewolf_appearance_data(self) -> List[WerewolfAppearanceExcelData]:
        """获取所有狼人杀外观数据"""
        return self._werewolf_appearance_valid_rows

###################################################################################################
###################################################################################################

_cache_excel_data_manager: Optional[ExcelDataManager] = None


def get_excel_data_manager() -> ExcelDataManager:
    global _cache_excel_data_manager
    if _cache_excel_data_manager is None:
        # 创建全局单例实例 - 只加载狼人杀外观数据
        assert Path("excel_test.xlsx").exists(), "Excel test file does not exist."
        _cache_excel_data_manager = ExcelDataManager(
            excel_file_path=Path("excel_test.xlsx"),
            werewolf_appearance_sheet_name="werewolf_appearances",  # 只加载狼人杀外观数据
        )

    assert _cache_excel_data_manager is not None, "ExcelDataManager is not initialized."
    return _cache_excel_data_manager
