
from typing import override, Set
from entitas import Matcher, ExecuteProcessor, Group, Entity #type: ignore
from ecs_systems.components import DestroyComponent
from my_entitas.extended_context import ExtendedContext
from loguru import logger
   
#### 这个类不允许再动了，基本固定了。
class DestroySystem(ExecuteProcessor):
    
    def __init__(self, context: ExtendedContext) -> None:
        self._context: ExtendedContext = context
####################################################################################################################################
    @override
    def execute(self) -> None:
        self._handle()
####################################################################################################################################
    def _handle(self) -> None:
        entityGroup: Group = self._context.get_group(Matcher(DestroyComponent))
        entities: Set[Entity] = entityGroup.entities
        #不能够一边遍历一边删除，所以先复制一份
        entities_copy = entities.copy()
        while len(entities_copy) > 0:
             destory_entity = entities_copy.pop() 
             self._context.destroy_entity(destory_entity)
####################################################################################################################################