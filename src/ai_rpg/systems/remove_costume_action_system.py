"""脱下时装动作系统模块。"""

from typing import final, override, Dict, List, Final
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    RemoveCostumeAction,
    AppearanceComponent,
    AppearanceUpdateEvent,
    WornCostumeComponent,
    StorageComponent,
)
from ..models.items import CostumeItem
from .appearance_prompt_builders import build_remove_costume_message


############################################################################################################
@final
class RemoveCostumeActionSystem(ReactiveProcessor):

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(RemoveCostumeAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(RemoveCostumeAction, AppearanceComponent)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        # 处理每个触发脱装动作的实体
        for entity in entities:
            self._remove_costume(entity)

    ####################################################################################################################################
    def _remove_costume(self, entity: Entity) -> None:
        """脱装：取出 WornCostumeComponent.item，移除组件，归还全局 StorageComponent，
        重置外观为基础体型，并广播外观更新事件。无时装则静默跳过。"""

        if not entity.has(WornCostumeComponent):
            return

        costume_item: CostumeItem = entity.get(WornCostumeComponent).item
        entity.remove(WornCostumeComponent)

        # 归还全局储物箱
        storage_entity = self._game.get_storage_entity()
        assert storage_entity is not None, "找不到全局储物箱实体"
        assert storage_entity.has(
            StorageComponent
        ), "全局储物箱实体缺少 StorageComponent"
        storage_entity.get(StorageComponent).items.append(costume_item)

        # 重置外观为基础体型
        appearance_comp = entity.get(AppearanceComponent)
        entity.replace(
            AppearanceComponent,
            appearance_comp.name,
            appearance_comp.base_body,
            appearance_comp.base_body,
        )
        logger.debug(
            f"角色 {entity.name} 已移除时装 {costume_item.name!r}，外观重置为基础体型"
        )

        # 广播外观更新事件，通知前端或其他系统角色外观已恢复为基础体型
        stage_entity = self._game.resolve_stage_entity(entity)
        assert stage_entity is not None, "actor无所在场景是有问题的"
        self._game.broadcast_to_stage(
            entity,
            AppearanceUpdateEvent(
                message=build_remove_costume_message(
                    entity.name, appearance_comp.base_body
                ),
                actor=entity.name,
                stage=stage_entity.name,
                appearance=appearance_comp.base_body,
            ),
        )
