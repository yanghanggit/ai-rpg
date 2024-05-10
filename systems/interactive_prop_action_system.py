from typing import Optional
from loguru import logger
from auxiliary.actor_action import ActorAction
from auxiliary.base_data import PropDataProxy
from auxiliary.components import InteractivePropActionComponent, UseInteractivePropActionComponent
from auxiliary.dialogue_rule import parse_target_and_message
from auxiliary.extended_context import ExtendedContext
from auxiliary.file_def import PropFile
from entitas import Entity, Matcher, ReactiveProcessor # type: ignore
from auxiliary.director_component import notify_stage_director
from entitas.group import GroupEvent
from auxiliary.director_event import NPCInteractivePropEvent
from auxiliary.format_of_complex_intertactive_props import parse_complex_interactive_props

class InteractivePropActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(UseInteractivePropActionComponent): GroupEvent.ADDED }
    
    def filter(self, entity: Entity) -> bool:
        return entity.has(UseInteractivePropActionComponent)
    
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.useprop(entity)

    def useprop(self, entity: Entity) -> None:
        interactive_prop_comp: UseInteractivePropActionComponent = entity.get(UseInteractivePropActionComponent)
        interactive_prop_action: ActorAction = interactive_prop_comp.action
        for value in interactive_prop_action.values:
            parse = parse_target_and_message(value)
            targetname: Optional[str] = parse[0]
            assert targetname is not None
            propname: Optional[str] = parse[1]
            assert propname is not None
            if self._interactive_prop_(entity, targetname, propname): 
                logger.debug(f"InteractivePropActionSystem: {targetname} is using {propname}")
                user_name = self.context.safe_get_entity_name(entity)
                notify_stage_director(self.context, entity, NPCInteractivePropEvent(user_name, targetname, propname))

    def _interactive_prop_(self, entity: Entity, targetname: str, propname: str) -> bool:
        filesystem = self.context.file_system
        username = self.context.safe_get_entity_name(entity)

        if not filesystem.has_prop_file(username, propname):
            logger.error(f"{username}身上没有{propname}，请检查。")
            return False
        
        interactivepropresult = self.check_target_with_prop(targetname, propname)
        assert interactivepropresult is not None
        propdata = PropDataProxy(interactivepropresult)
        if interactivepropresult is None:
            logger.warning(f"{targetname}与{propname}之间的关系未定义，请检查。")
            return False
        
        if not filesystem.has_prop_file(username, interactivepropresult):
            createpropfile = PropFile(interactivepropresult, username, propdata)
            filesystem.add_prop_file(createpropfile)
        else:
            logger.error(f"{username}已经达成{interactivepropresult},请检查结果是否正确。")
            return False

        return True
        
    
    def check_target_with_prop(self, targetname: str, propname: str) -> Optional[str]:
        stage_entity: Optional[Entity] = self.context.getstage(targetname)
        if stage_entity is not None and stage_entity.has(InteractivePropActionComponent):
            stage_interative_prop_comp: InteractivePropActionComponent = stage_entity.get(InteractivePropActionComponent)
            stage_interative_props: str = stage_interative_prop_comp.interactive_props
            interactive_props: list[str] = parse_complex_interactive_props(stage_interative_props)
            if propname == interactive_props[0]:
                return interactive_props[1]

        return None

        