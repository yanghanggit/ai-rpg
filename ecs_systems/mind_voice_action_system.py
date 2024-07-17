from typing import override
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from ecs_systems.components import MindVoiceActionComponent
from my_entitas.extended_context import ExtendedContext

####################################################################################################
class MindVoiceActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self._context = context
####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(MindVoiceActionComponent): GroupEvent.ADDED}
####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(MindVoiceActionComponent)
####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        # 核心处理
        for entity in entities:
            self.mindvoice(entity)      
####################################################################################################
    def mindvoice(self, entity: Entity) -> None:
        pass
 ####################################################################################################       
                