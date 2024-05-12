from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (CheckStatusActionComponent, SimpleRPGRoleComponent)
from loguru import logger
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import NPCCheckStatusEvent
from typing import List
from auxiliary.base_data import PropData


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
        logger.debug(f"{safename} is checking status")
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
###################################################################################################################       




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
        logger.debug(f"{safe_npc_name} is checking status")
        #
        helper = CheckStatusActionHelper(self.context)
        helper.check_status(entity)
        #
        notify_stage_director(self.context, entity, NPCCheckStatusEvent(safe_npc_name, helper.props, helper.health, helper.role_components, helper.events))
###################################################################################################################
    