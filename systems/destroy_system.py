
from entitas import Matcher, ExecuteProcessor, Group, Entity #type: ignore
from auxiliary.components import DestroyComponent
from auxiliary.extended_context import ExtendedContext
from loguru import logger
   
#### 这个类不允许再动了，基本固定了。
class DestroySystem(ExecuteProcessor):
    
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context

    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  DestroySystem  >>>>>>>>>>>>>>>>>")
        self.handledestroy()

    def handledestroy(self) -> None:
        entityGroup: Group = self.context.get_group(Matcher(DestroyComponent))
        entities: set[Entity] = entityGroup.entities
        #不能够一边遍历一边删除，所以先复制一份
        entities_copy = entities.copy()
        while len(entities_copy) > 0:
             destory_entity = entities_copy.pop() 
             self.context.destroy_entity(destory_entity)