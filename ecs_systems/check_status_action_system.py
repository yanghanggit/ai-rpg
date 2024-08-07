from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from my_entitas.extended_context import ExtendedContext
from ecs_systems.action_components import (CheckStatusActionComponent, DeadActionComponent)
from ecs_systems.components import SimpleRPGAttrComponent, ActorComponent
from ecs_systems.stage_director_component import notify_stage_director
from typing import List, override
from file_system.files_def import PropFile
from builtin_prompt.cn_builtin_prompt import check_status_action_prompt
from ecs_systems.stage_director_event import IStageDirectorEvent

####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class CheckStatusActionHelper:

    def __init__(self, context: ExtendedContext):

        self._context: ExtendedContext = context
        self._prop_files_as_weapon_clothes_non_consumable_item: List[PropFile] = []
        self._maxhp: int = 0
        self._hp: int = 0
        self._prop_files_as_special_components: List[PropFile] = []

    def clear(self) -> None:
        self._prop_files_as_weapon_clothes_non_consumable_item.clear()
        self._maxhp = 0
        self._hp = 0
        self._prop_files_as_special_components.clear()

    def check_props(self, entity: Entity) -> None:
        safename = self._context.safe_get_entity_name(entity)
        prop_files = self._context._file_system.get_prop_files(safename)
        for prop_file in prop_files:
            if prop_file.is_weapon or prop_file.is_clothes or prop_file.is_non_consumable_item:
                self._prop_files_as_weapon_clothes_non_consumable_item.append(prop_file)
            elif prop_file.is_special_component:
                self._prop_files_as_special_components.append(prop_file)
            
    def check_health(self, entity: Entity) -> None:
        if not entity.has(SimpleRPGAttrComponent):
            return 
        rpg_attr_comp = entity.get(SimpleRPGAttrComponent)
        self._maxhp = rpg_attr_comp.maxhp
        self._hp = rpg_attr_comp.hp

    def check_status(self, entity: Entity) -> None:
        # 先清空
        self.clear()
        # 检查道具
        self.check_props(entity)
        # 检查生命值
        self.check_health(entity)

    @property
    def health(self) -> float:
        return self._hp / self._maxhp
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################        
class ActorCheckStatusEvent(IStageDirectorEvent):

    def __init__(self, who: str, props: List[PropFile], health: float, special_components: List[PropFile]) -> None:
        self._who: str = who
        self._prop_files_as_weapon_clothes_non_consumable_item: List[PropFile] = props
        self._health: float = health
        self._prop_files_as_special_components: List[PropFile] = special_components

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self._who:
            # 只有自己知道
            return ""
        return check_status_action_prompt(self._who, self._prop_files_as_weapon_clothes_non_consumable_item, self._health, self._prop_files_as_special_components)
    
    def to_stage(self, stage_name: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class CheckStatusActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self._context: ExtendedContext = context
####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(CheckStatusActionComponent): GroupEvent.ADDED }
####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(CheckStatusActionComponent) and entity.has(ActorComponent)  and not entity.has(DeadActionComponent)
####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.check_status(entity)
####################################################################################################################################
    # 临时写成这样，就是检查自己有哪些道具
    def check_status(self, entity: Entity) -> None:
        safe_name = self._context.safe_get_entity_name(entity)
        #
        helper = CheckStatusActionHelper(self._context)
        helper.check_status(entity)
        #
        notify_stage_director(self._context, entity, 
                              ActorCheckStatusEvent(safe_name, 
                                                    helper._prop_files_as_weapon_clothes_non_consumable_item, 
                                                    helper.health, 
                                                    helper._prop_files_as_special_components))
####################################################################################################################################
    