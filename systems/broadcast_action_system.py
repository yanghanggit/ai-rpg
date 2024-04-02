
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import BroadcastActionComponent, StageComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from auxiliary.print_in_color import Color
from auxiliary.prompt_maker import broadcast_action_prompt
#from typing import Optional
from loguru import logger
from director_component import DirectorComponent
from director_event import BroadcastEvent

class BroadcastActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(BroadcastActionComponent): GroupEvent.ADDED}

    def filter(self, entity: Entity) -> bool:
        return entity.has(BroadcastActionComponent)

    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  BroadcastActionSystem  >>>>>>>>>>>>>>>>>")

        for entity in entities:
            self.handlebroadcast(entity)  # 核心处理

        for entity in entities:
            entity.remove(BroadcastActionComponent)  # 必须移除！！！       

    ## 目前的设定是场景与NPC都能广播，后续会调整与修改。
    def handlebroadcast(self, entity: Entity) -> None:
        ## 没有场景不需要广播
        stageentity = self.context.get_stage_entity_by_uncertain_entity(entity)
        if stageentity is None:
            logger.error(f"BroadcastActionSystem: stageentity is None!")
            return
        #
        broadcastcomp: BroadcastActionComponent = entity.get(BroadcastActionComponent)
        stagecomp: StageComponent = stageentity.get(StageComponent)
        #
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        # 遍历处理
        action: ActorAction = broadcastcomp.action
        for value in action.values:
            ## 原始处理
            broadcast_say = broadcast_action_prompt(action.name, stagecomp.name, value, self.context)
            logger.info(f"{Color.HEADER}{broadcast_say}{Color.ENDC}")
            stagecomp.directorscripts.append(broadcast_say)
            ## 重构处理
            event = BroadcastEvent(action.name, stagecomp.name, value)
            directorcomp.addevent(event)
            
        
                