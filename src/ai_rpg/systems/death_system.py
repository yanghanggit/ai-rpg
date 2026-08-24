"""死亡处理系统模块。"""

from typing import Final, final, override

from loguru import logger

from ..entitas import ExecuteProcessor, Matcher
from ..game.dbg_combat_processor import compute_character_stats
from ..game.dbg_game import DBGGame
from ..models import (
    CharacterStatsComponent,
    DeathComponent,
    HumanMessage,
)


###############################################################################################################################################
def _build_death_notification() -> str:
    """生成角色 HP 归零失去战斗能力的通知文本。"""
    return "# 你的HP已归零，失去战斗能力！"


###############################################################################################################################################
@final
class DeathSystem(ExecuteProcessor):
    """
    死亡处理系统：将 HP 归零且尚未标记死亡的实体标记为死亡。
    """

    ############################################################################################################
    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:
        defeated_entities = self._game.get_group(
            Matcher(all_of=[CharacterStatsComponent], none_of=[DeathComponent])
        ).entities.copy()

        for entity in defeated_entities:
            entity_hp = compute_character_stats(entity).hp
            if entity_hp <= 0:
                logger.info(f"{entity.name} 已被击败，HP={entity_hp}")
                self._game.add_human_message(
                    entity, HumanMessage(content=_build_death_notification())
                )
                entity.replace(DeathComponent, entity.name)
