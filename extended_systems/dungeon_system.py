from typing import Final, List, Optional, final
from loguru import logger
from models.v_0_0_1 import StageInstance
from extended_systems.combat_system import CombatSystem


# TODO临时的，先管理下。
@final
class DungeonSystem:

    ########################################################################################################################
    def __init__(
        self,
        prefix_name: str,
        dungeon_levels: List[StageInstance],
    ) -> None:

        # 初始化。
        self._prefix_name: Final[str] = prefix_name
        self._levels: List[StageInstance] = dungeon_levels
        self._combat_system: CombatSystem = CombatSystem()
        self._position: int = 0

        #
        if len(self._levels) > 0:
            logger.info(
                f"初始化地下城系统 = [{self.name}]\n地下城数量：{len(self._levels)}"
            )
            for stage in self._levels:
                logger.info(f"地下城关卡：{stage.name}")

    ########################################################################################################################
    @property
    def name(self) -> str:
        if len(self._levels) == 0:
            return "EmptyDungeon"
        dungeon_stage_names = "-".join([stage.name for stage in self._levels])
        return f"{self._prefix_name}-{dungeon_stage_names}"

    ########################################################################################################################
    @property
    def dungeon_levels(self) -> List[StageInstance]:
        return self._levels

    ########################################################################################################################
    @property
    def combat_system(self) -> CombatSystem:
        return self._combat_system

    ########################################################################################################################
    @property
    def position(self) -> int:
        return self._position

    ########################################################################################################################
    def next_level(self) -> Optional[StageInstance]:
        if self._position + 1 < len(self._levels):
            self._position += 1
            return self._levels[self._position]
        return None

    ########################################################################################################################
    def advance_to_next_level(self, stage_name: str = "") -> bool:

        assert len(self._levels) > 0, "地下城系统为空！"
        if len(self._levels) == 0:
            logger.warning("地下城系统为空！")
            return False

        assert self._position < len(self._levels), "当前地下城关卡已经完成！"
        if self._position >= len(self._levels):
            logger.warning("当前地下城关卡已经完成！")
            return False

        current_level_stage = self._levels[self._position]
        assert current_level_stage.name == stage_name, "当前地下城关卡已经完成！"
        self._position = self._position + 1
        return True

    ########################################################################################################################
