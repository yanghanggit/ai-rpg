from typing import override
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import TagActionComponent
from my_entitas.extended_context import ExtendedContext
from loguru import logger

####################################################################################################
class TagActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(TagActionComponent): GroupEvent.ADDED}
####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(TagActionComponent)
####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        pass
####################################################################################################