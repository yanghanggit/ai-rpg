from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (CheckStatusActionComponent, SimpleRPGRoleComponent)
from loguru import logger
from auxiliary.director_component import notify_stage_director
from typing import List
from auxiliary.base_data import PropData
from auxiliary.cn_builtin_prompt import check_status_action_prompt
from auxiliary.director_event import IDirectorEvent

####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class CheckStatusActionHelper:
    def __init__(self, context: ExtendedContext):
        self.context = context
        self.props: List[PropData] = []
        self.maxhp = 0
        self.hp = 0
        self.role_components: List[PropData] = []
        self.events: List[PropData] = []

    def clear(self) -> None:
        self.props.clear()
        self.maxhp = 0
        self.hp = 0

    def check_props(self, entity: Entity) -> None:
        safename = self.context.safe_get_entity_name(entity)
        #logger.debug(f"{safename} is checking status")
        filesystem = self.context.file_system
        files = filesystem.get_prop_files(safename)
        for file in files:
            if file.prop.is_weapon() or file.prop.is_clothes() or file.prop.is_non_consumable_item():
                self.props.append(file.prop)
            elif file.prop.is_role_component():
                self.role_components.append(file.prop)
            elif file.prop.is_event():
                self.events.append(file.prop)
            
    def check_health(self, entity: Entity) -> None:
        if not entity.has(SimpleRPGRoleComponent):
            return 
        rpgcomp: SimpleRPGRoleComponent = entity.get(SimpleRPGRoleComponent)
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
class NPCCheckStatusEvent(IDirectorEvent):

    def __init__(self, who: str, props: List[PropData], health: float, role_components: List[PropData], events: List[PropData]) -> None:
        self.who = who
        self.props = props
        self.health = health
        self.role_comps = role_components
        self.events = events

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.who:
            # 只有自己知道
            return ""
        return check_status_action_prompt(self.who, self.props, self.health, self.role_comps, self.events)
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class CheckStatusActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(CheckStatusActionComponent): GroupEvent.ADDED }
###################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(CheckStatusActionComponent)
###################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.check_status(entity)
###################################################################################################################
    # 临时写成这样，就是检查自己有哪些道具
    def check_status(self, entity: Entity) -> None:
        safe_npc_name = self.context.safe_get_entity_name(entity)
        #logger.debug(f"{safe_npc_name} is checking status")
        #
        helper = CheckStatusActionHelper(self.context)
        helper.check_status(entity)
        #
        notify_stage_director(self.context, entity, NPCCheckStatusEvent(safe_npc_name, helper.props, helper.health, helper.role_components, helper.events))
###################################################################################################################
    