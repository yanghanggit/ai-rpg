from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from my_entitas.extended_context import ExtendedContext
from ecs_systems.components import (CheckStatusActionComponent, SimpleRPGAttrComponent, ActorComponent, DeadActionComponent)
from loguru import logger
from ecs_systems.stage_director_component import notify_stage_director
from typing import List, override
from prototype_data.data_def import PropData
from builtin_prompt.cn_builtin_prompt import check_status_action_prompt
from ecs_systems.stage_director_event import IStageDirectorEvent

####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class CheckStatusActionHelper:
    def __init__(self, context: ExtendedContext):
        self.context = context
        self.props: List[PropData] = []
        self.maxhp = 0
        self.hp = 0
        self.special_components: List[PropData] = []
        self.events: List[PropData] = []

    def clear(self) -> None:
        self.props.clear()
        self.maxhp = 0
        self.hp = 0

    def check_props(self, entity: Entity) -> None:
        safename = self.context.safe_get_entity_name(entity)
        #logger.debug(f"{safename} is checking status")
        filesystem = self.context._file_system
        files = filesystem.get_prop_files(safename)
        for file in files:
            if file._prop.is_weapon() or file._prop.is_clothes() or file._prop.is_non_consumable_item():
                self.props.append(file._prop)
            elif file._prop.is_special_component():
                self.special_components.append(file._prop)
            
    def check_health(self, entity: Entity) -> None:
        if not entity.has(SimpleRPGAttrComponent):
            return 
        rpgcomp: SimpleRPGAttrComponent = entity.get(SimpleRPGAttrComponent)
        self.maxhp = rpgcomp.maxhp
        self.hp = rpgcomp.hp

    def check_status(self, entity: Entity) -> None:
        # 先清空
        self.clear()
        # 检查道具
        self.check_props(entity)
        # 检查生命值
        self.check_health(entity)

    @property
    def health(self) -> float:
        return self.hp / self.maxhp
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################        
class ActorCheckStatusEvent(IStageDirectorEvent):

    def __init__(self, who: str, props: List[PropData], health: float, special_components: List[PropData], events: List[PropData]) -> None:
        self.who = who
        self.props = props
        self.health = health
        self.special_components = special_components
        self.events = events

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self.who:
            # 只有自己知道
            return ""
        return check_status_action_prompt(self.who, self.props, self.health, self.special_components, self.events)
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class CheckStatusActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(CheckStatusActionComponent): GroupEvent.ADDED }
###################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(CheckStatusActionComponent) and entity.has(ActorComponent)  and not entity.has(DeadActionComponent)
###################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.check_status(entity)
###################################################################################################################
    # 临时写成这样，就是检查自己有哪些道具
    def check_status(self, entity: Entity) -> None:
        safe_name = self.context.safe_get_entity_name(entity)
        #
        helper = CheckStatusActionHelper(self.context)
        helper.check_status(entity)
        #
        notify_stage_director(self.context, entity, ActorCheckStatusEvent(safe_name, helper.props, helper.health, helper.special_components, helper.events))
###################################################################################################################
    