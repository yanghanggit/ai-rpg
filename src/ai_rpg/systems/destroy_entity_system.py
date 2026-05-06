"""销毁所有持有 DestroyComponent 的实体，每帧执行一次。"""

from typing import final, override
from loguru import logger
from ..entitas import ExecuteProcessor, Matcher
from ..game.rpg_game import RPGGame
from ..models import DestroyComponent


@final
class DestroyEntitySystem(ExecuteProcessor):
    """每帧查找持有 DestroyComponent 的实体并将其销毁。

    用法：注册为 ExecuteProcessor，向实体添加 DestroyComponent 即可标记其待销毁。
    """

    def __init__(self, game: RPGGame) -> None:
        self._game: RPGGame = game

    ####################################################################################################################################
    @override
    async def execute(self) -> None:
        """销毁所有持有 DestroyComponent 的实体。"""

        # 查找所有待销毁实体！
        destroyable_entities = self._game.get_group(
            Matcher(DestroyComponent)
        ).entities.copy()

        # 销毁所有待销毁实体！
        while len(destroyable_entities) > 0:
            destory_entity = destroyable_entities.pop()
            self._game.destroy_entity(destory_entity)
            logger.debug(f"Destroy entity: {destory_entity.name}")

    ####################################################################################################################################
