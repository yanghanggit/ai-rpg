from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher
from .base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    WitchCureAction,
    SDWitchItemName,
    InventoryComponent,
    AgentEvent,
    NightKillMarkerComponent,
    DeathComponent,
)
from loguru import logger


####################################################################################################################################
@final
class WitchCureActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(WitchCureAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(WitchCureAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_action(entity)

    ####################################################################################################################################
    def _process_action(self, entity: Entity) -> None:

        # logger.debug(f"💊 处理女巫救治行动 = {entity.name}")

        witch_cure_action = entity.get(WitchCureAction)
        assert entity.name == witch_cure_action.name, "实体名称和目标名称不匹配"

        witch_entity = self._game.get_entity_by_name(witch_cure_action.witch_name)
        assert witch_entity is not None, "找不到女巫实体"
        if witch_entity is None:
            logger.error(f"找不到女巫实体 = {witch_cure_action.witch_name}")
            return

        inventory_component = witch_entity.get(InventoryComponent)
        assert inventory_component is not None, "女巫实体没有道具组件"

        cure_item = inventory_component.find_item(SDWitchItemName.CURE)
        assert cure_item is not None, "女巫没有解药，无法使用解药"
        if cure_item is None:
            logger.warning(f"女巫 {witch_entity.name} 没有解药，无法使用解药")
            self._game.notify_entities(
                set({witch_entity}),
                AgentEvent(
                    message=f"# 提示！你没有解药，无法对 {entity.name} 使用解药。",
                ),
            )
            return

        if entity.has(NightKillMarkerComponent):
            entity.remove(NightKillMarkerComponent)
            logger.info(
                f"女巫 {witch_entity.name} 使用了解药，救活了玩家 {entity.name}, 移除了夜晚死亡标记"
            )

        if entity.has(DeathComponent):
            entity.remove(DeathComponent)
            logger.info(
                f"女巫 {witch_entity.name} 使用了解药，救活了玩家 {entity.name}, 移除了死亡组件"
            )

        # 移除解药道具
        inventory_component.items.remove(cure_item)

        # 通知女巫使用解药成功
        self._game.notify_entities(
            set({witch_entity}),
            AgentEvent(
                message=f"# 女巫 {witch_entity.name} 使用了解药，成功救活了玩家 {entity.name}, 并且解药已被使用。",
            ),
        )

    ####################################################################################################################################
