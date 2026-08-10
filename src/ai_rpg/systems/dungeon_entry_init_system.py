"""副本入口初始化系统：为副本全部角色触发牌库生成。"""

from typing import Final, final, override
from loguru import logger
from ..entitas import ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..models import (
    GenerateDeckAction,
    MonsterComponent,
    PartyMemberComponent,
)


###################################################################################################################################################################
@final
class DungeonEntryInitSystem(ExecuteProcessor):
    """副本入口初始化系统。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:
        logger.info("[DungeonEntryInitSystem] 为副本全部角色添加牌库生成动作…")

        count = 0

        # 远征队成员（玩家及其队友）
        party_entities = self._game.get_group(
            Matcher(all_of=[PartyMemberComponent])
        ).entities.copy()
        for entity in party_entities:
            entity.replace(GenerateDeckAction, entity.name)
            logger.debug(f"[{entity.name}] 已添加 GenerateDeckAction（远征队）")
            count += 1

        # 全部怪物
        monster_entities = self._game.get_group(
            Matcher(all_of=[MonsterComponent])
        ).entities.copy()
        for entity in monster_entities:
            entity.replace(GenerateDeckAction, entity.name)
            logger.debug(f"[{entity.name}] 已添加 GenerateDeckAction（怪物）")
            count += 1

        logger.info(
            f"[DungeonEntryInitSystem] 完成，已为 {count} 个角色添加 GenerateDeckAction"
        )


###################################################################################################################################################################
