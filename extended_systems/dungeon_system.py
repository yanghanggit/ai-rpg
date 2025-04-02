from typing import Optional, final
from loguru import logger
from models.v_0_0_1 import Stage, Dungeon
from extended_systems.engagement_system import EngagementSystem


# TODO临时的，先管理下。
@final
class DungeonSystem(Dungeon):

    @property
    def engagement_system(self) -> EngagementSystem:
        assert self.engagement is not None
        assert isinstance(self.engagement, EngagementSystem)
        return self.engagement

    ########################################################################################################################
    def current_level(self) -> Optional[Stage]:
        if len(self.levels) == 0:
            logger.warning("地下城系统为空！")
            return None

        if self.position >= len(self.levels):
            logger.warning("当前地下城关卡已经完成！")
            return None

        return self.levels[self.position]

    ########################################################################################################################
    def next_level(self) -> Optional[Stage]:

        if len(self.levels) == 0:
            logger.warning("地下城系统为空！")
            return None

        if self.position >= len(self.levels):
            logger.warning("当前地下城关卡已经完成！")
            return None

        return (
            self.levels[self.position + 1]
            if self.position + 1 < len(self.levels)
            else None
        )

    ########################################################################################################################
    def advance_level(self) -> bool:

        if len(self.levels) == 0:
            logger.warning("地下城系统为空！")
            return False

        if self.position >= len(self.levels):
            logger.warning("当前地下城关卡已经完成！")
            return False

        self.position += 1
        return True

    ########################################################################################################################
