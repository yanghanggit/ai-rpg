"""副本生成收尾系统：无论成败清空中间产物并重置生成实体的记忆。"""

from typing import Final, final, override

from loguru import logger

from ..entitas import ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..models import DungeonGenerationComponent, WorldComponent


####################################################################################################################################
@final
class DungeonGenerationCleanupSystem(ExecuteProcessor):
    """无条件清空副本生成的中间过程数据，并重置生成实体的 agent memory。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    async def execute(self) -> None:
        # 清空中间过程数据：无论流程成功与否，本次生成到此为止
        self._game._dungeon_draft = None

        # 重置副本生成系统实体的记忆，仅保留首条 system prompt
        entities = self._game.get_group(
            Matcher(all_of=[WorldComponent, DungeonGenerationComponent])
        ).entities.copy()
        assert len(entities) == 1, "存在多个副本生成系统实体，数据异常"
        generation_entity = next(iter(entities))
        self._game.reset_agent_memory(generation_entity)
        logger.info(
            f"[DungeonGenerationCleanupSystem] 已清空中间过程数据并重置记忆: {generation_entity.name}"
        )
