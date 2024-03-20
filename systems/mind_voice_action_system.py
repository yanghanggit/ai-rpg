
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import MindVoiceActionComponent, StageComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from agents.tools.print_in_color import Color
from typing import Optional
from loguru import logger # type: ignore

class MindVoiceActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(MindVoiceActionComponent): GroupEvent.ADDED}

    def filter(self, entity: Entity) -> bool:
        return entity.has(MindVoiceActionComponent)

    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  MindVoiceActionSystem  >>>>>>>>>>>>>>>>>")

        # 核心处理
        for entity in entities:
            self.handle(entity)
            
        # 必须移除！！！
        for entity in entities:
            entity.remove(MindVoiceActionComponent)         

    def handle(self, entity: Entity) -> None:
        mindvoicecomp: MindVoiceActionComponent = entity.get(MindVoiceActionComponent)
        stagecomp: Optional[StageComponent] = self.context.get_stagecomponent_by_uncertain_entity(entity)
        if stagecomp is None or mindvoicecomp is None:
            return
        action: ActorAction = mindvoicecomp.action
        for value in action.values:
            #纯测试，暂时无用
            what_to_said = f"{action.name},心里想到:{value}"
            logger.info(f"{Color.BLUE}{what_to_said}{Color.ENDC}")
            
        
                