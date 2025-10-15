from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher
from .base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    SeerCheckAction,
    WerewolfComponent,
    AgentEvent,
)
from loguru import logger


####################################################################################################################################
@final
class SeerCheckActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SeerCheckAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SeerCheckAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_action(entity)

    ####################################################################################################################################
    def _process_action(self, entity: Entity) -> None:
        # logger.debug(f"🔮 处理预言家查验行动 = {entity.name} <=== 在被查")

        seer_check_action = entity.get(SeerCheckAction)
        assert entity.name == seer_check_action.name, "实体名称和目标名称不匹配"

        seer_entity = self._game.get_entity_by_name(seer_check_action.seer_name)
        assert seer_entity is not None, "找不到预言家实体"
        if seer_entity is None:
            logger.error(f"找不到预言家实体 = {seer_check_action.seer_name}")
            return

        # logger.debug(
        #     f"预言家查验行动的执行者 = {seer_check_action.seer_name},  ==> {entity.name}"
        # )

        # 揭示查看结果
        if entity.has(WerewolfComponent):
            logger.info(f"预言家查看的玩家 {entity.name} 是 狼人")
            self._game.notify_entities(
                set({seer_entity}),
                AgentEvent(
                    message=f"# 预言家 {seer_entity.name} 查验结果：玩家 {entity.name} 是 狼人！"
                ),
            )
        else:
            logger.info(f"预言家查看的玩家 {entity.name} 不是 狼人")
            self._game.notify_entities(
                set({seer_entity}),
                AgentEvent(
                    message=f"# 预言家 {seer_entity.name} 查验结果：玩家 {entity.name} 不是 狼人。"
                ),
            )

    ####################################################################################################################################
