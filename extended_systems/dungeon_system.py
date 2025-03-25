from typing import Final, List, Optional, Set, final
from loguru import logger
from models.v_0_0_1 import StageInstance
from extended_systems.combat_system import CombatSystem


# TODO临时的，先管理下。
@final
class DungeonSystem:

    ########################################################################################################################
    def __init__(
        self, prefix_name: str, stages: List[StageInstance], combat_system: CombatSystem
    ) -> None:

        # 初始化。
        self._prefix_name: Final[str] = prefix_name
        self._dungeon_levels: List[StageInstance] = stages
        self._completed_stages: Set[str] = set()
        self._combat_system: CombatSystem = combat_system

        #
        if len(self._dungeon_levels) > 0:
            logger.info(
                f"初始化地下城系统 = [{self.name}]\n地下城数量：{len(self._dungeon_levels)}"
            )
            for stage in self._dungeon_levels:
                logger.info(f"地下城关卡：{stage.name}")

    ########################################################################################################################
    @property
    def name(self) -> str:
        if len(self._dungeon_levels) == 0:
            return "EmptyDungeon"
        dungeon_stage_names = "-".join([stage.name for stage in self._dungeon_levels])
        return f"{self._prefix_name}-{dungeon_stage_names}"

    ########################################################################################################################
    @property
    def combat_system(self) -> CombatSystem:
        return self._combat_system

    ########################################################################################################################
    # TODO，输入一个名字，就能查看是否有下一个地下城。
    def get_next_dungeon_level(self, stage_name: str) -> Optional[StageInstance]:
        assert stage_name != "", "stage_name 不能为空！"
        for i, stage in enumerate(self._dungeon_levels):
            if stage.name == stage_name:
                if i + 1 < len(self._dungeon_levels):
                    return self._dungeon_levels[i + 1]
                else:
                    return None
        return None

    ########################################################################################################################
    def mark_stage_complete(self, stage_name: str) -> None:
        
        if len(self._dungeon_levels) == 0:
            logger.warning("地下城系统为空！")
            return

        # 如果 stage_name 不在 self._stages 中，就报错。
        assert stage_name in [
            stage.name for stage in self._dungeon_levels
        ], f"{stage_name} 不在 self._stages 中！"
        # 如果 stage_name 已经在 self._finished_stages 中，就报错。
        assert (
            stage_name not in self._completed_stages
        ), f"{stage_name} 已经在 self._finished_stages 中！"

        # 最终添加。
        self._completed_stages.add(stage_name)
        logger.info(f"完成地下城关卡：{stage_name}")

    ########################################################################################################################


# 全局空
EMPTY_DUNGEON: Final[DungeonSystem] = DungeonSystem("", [], CombatSystem())
# #######################################################################################################################################
