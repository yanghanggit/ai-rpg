from typing import Optional
from loguru import logger
from auxiliary.actor_action import ActorAction
from auxiliary.components import InteractivePropActionComponent
from auxiliary.dialogue_rule import parse_target_and_message
from auxiliary.extended_context import ExtendedContext
from auxiliary.file_def import InteractivePropFile
from entitas import Entity, Matcher, ReactiveProcessor
from auxiliary.director_component import notify_stage_director
from entitas.group import GroupEvent
from auxiliary.director_event import NPCInteractivePropEvent

class InteractivePropActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(InteractivePropActionComponent): GroupEvent.ADDED }
    
    def filter(self, entity: Entity) -> bool:
        return entity.has(InteractivePropActionComponent)
    
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  InteractivePropActionSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            self.useprop(entity)

    def useprop(self, entity: Entity) -> None:
        interactive_prop_comp: InteractivePropActionComponent = entity.get(InteractivePropActionComponent)
        interactive_prop_action: ActorAction = interactive_prop_comp.action
        for value in interactive_prop_action.values:
            parse = parse_target_and_message(value)
            targetname: Optional[str] = parse[0]
            propname: Optional[str] = parse[1]
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
        if interactivepropresult is None:
            logger.warning(f"{targetname}与{propname}之间的关系未定义，请检查。")
            return False
        
        if not filesystem.has_interactivepropfile(username, interactivepropresult):
            createpropfile = InteractivePropFile(username, targetname, interactivepropresult)
            filesystem.add_interactive_prop_to_target_file(createpropfile)
        else:
            logger.error(f"{username}已经达成{interactivepropresult},请检查结果是否正确。")
            return False

        return True
        
    
    def check_target_with_prop(self, targetname: str, propname: str) -> str:
        # 暂时在这里对于道具和作用对象的产物进行定义
        target_with_prop = { "禁言者之棺": ["腐朽的匕首"] }
        target_prompts = { "禁言者之棺": "的棺材盖" }
        prop_prompts = { "腐朽的匕首": "撬开" }

        for target, props in target_with_prop.items():
            if target == targetname:
                for prop in props:
                    if prop == propname:
                        return prop_prompts[prop] + target_prompts[target]
        return None

        