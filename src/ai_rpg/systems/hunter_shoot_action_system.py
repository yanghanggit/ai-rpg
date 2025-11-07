from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    HunterShootAction,
    DeathComponent,
)
from loguru import logger
from ..game.sdg_game import SDGGame


####################################################################################################################################
@final
class HunterShootActionSystem(ReactiveProcessor):
    """猎人射击动作执行系统（仅负责执行射击）"""

    def __init__(self, game_context: SDGGame) -> None:
        super().__init__(game_context)
        self._game: SDGGame = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(HunterShootAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(HunterShootAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_action(entity)

    ####################################################################################################################################
    def _process_action(self, entity: Entity) -> None:
        """处理猎人射击行动"""

        shoot_action = entity.get(HunterShootAction)
        assert entity.name == shoot_action.name, "实体名称和目标名称不匹配"

        hunter_entity = self._game.get_entity_by_name(shoot_action.hunter_name)
        if hunter_entity is None:
            logger.error(f"找不到猎人实体 = {shoot_action.hunter_name}")
            return

        # 检查目标是否已经死亡
        if entity.has(DeathComponent):
            logger.warning(
                f"猎人 {hunter_entity.name} 射击的目标 {entity.name} 已经死亡，无法再次射击"
            )
            return

        # 执行射击，标记目标死亡
        entity.replace(DeathComponent, entity.name)

        logger.info(
            f"猎人 {hunter_entity.name} 开枪射击了 {entity.name}，{entity.name} 已死亡"
        )

        # 通知所有玩家猎人的射击结果（公开信息）
        self._game.announce_to_players(
            f"# 猎人 {hunter_entity.name} 在死亡时开枪带走了 {entity.name}！"
        )

    ####################################################################################################################################
