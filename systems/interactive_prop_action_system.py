import re
from typing import Optional
from loguru import logger
from auxiliary.actor_action import ActorAction
from auxiliary.base_data import PropData
from auxiliary.components import InteractivePropActionComponent, UseInteractivePropActionComponent, CheckStatusActionComponent, NPCComponent, PrisonBreakActionComponent, ExitOfPrisonComponent
from auxiliary.dialogue_rule import parse_target_and_message
from auxiliary.extended_context import ExtendedContext
from auxiliary.file_def import PropFile
from entitas import Entity, Matcher, ReactiveProcessor # type: ignore
from auxiliary.director_component import notify_stage_director
from entitas.group import GroupEvent
from auxiliary.director_event import IDirectorEvent
from auxiliary.format_of_complex_intertactive_props import parse_complex_interactive_props
from typing import List
from auxiliary.cn_builtin_prompt import interactive_prop_action_success_prompt



####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCInteractivePropEvent(IDirectorEvent):

    def __init__(self, npcname: str, targetname: str, propname: str, interactive_action: str, interactive_result: str) -> None:
        self.npcname = npcname
        self.targetname = targetname
        self.propname = propname
        self.interactive_action = interactive_action
        self.interactive_result = interactive_result

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        return interactive_prop_action_success_prompt(self.npcname, self.targetname, self.propname, self.interactive_action, self.interactive_result)
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return interactive_prop_action_success_prompt(self.npcname, self.targetname, self.propname, self.interactive_action, self.interactive_result)

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
            use_prop_result = self.useprop(entity)
            if len(use_prop_result) > 0:
                self.after_use_prop_success(entity, use_prop_result)

    def useprop(self, entity: Entity) -> List[tuple[str, str]]:

        use_prop_result: List[tuple[str, str]] = []

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
                use_prop_result.append((targetname, propname))
        
        return use_prop_result

    def _interactive_prop_(self, entity: Entity, targetname: str, propname: str) -> bool:
        databasesystem = self.context.data_base_system
        filesystem = self.context.file_system
        username = self.context.safe_get_entity_name(entity)

        if not filesystem.has_prop_file(username, propname):
            logger.error(f"{username}身上没有{propname}，请检查。")
            return False
        
        interactivepropresult = self.check_target_with_prop(targetname, propname)
        if interactivepropresult is None:
            logger.warning(f"{targetname}与{propname}之间的关系未定义，请检查。")
            return False
        
        if databasesystem.get_prop(interactivepropresult) is None:
            logger.error(f"数据库不存在{interactivepropresult}，请检查。")
            return False
    
        if not filesystem.has_prop_file(username, interactivepropresult):
            propdata = databasesystem.get_prop(interactivepropresult)
            assert propdata is not None
            createpropfile = PropFile(interactivepropresult, username, propdata)
            filesystem.add_prop_file(createpropfile)
        else:
            logger.error(f"{username}已经达成{interactivepropresult},请检查结果是否正确。")
            return False
        
        interactiveaction = self.parse_interactive_prop_action(propdata, propname, targetname)
        if interactiveaction is None:
            logger.error(f"解析交互道具{propname}与{targetname}之间的关系失败，请检查。")
            return False
        notify_stage_director(self.context, entity, NPCInteractivePropEvent(username, targetname, propname, interactiveaction, interactivepropresult))

        return True
    

    def parse_interactive_prop_action(self, propdata: PropData, interactivepropname: str, targetname: str) -> Optional[str]:
        description = propdata.description
        pattern = rf"{interactivepropname}(.*?){targetname}"
        matchresult = re.search(pattern, description)
        if matchresult:
            return matchresult.group(1).strip()
        else:
            return None

        
    
    def check_target_with_prop(self, targetname: str, propname: str) -> Optional[str]:
        stage_entity: Optional[Entity] = self.context.getstage(targetname)
        if stage_entity is not None and stage_entity.has(InteractivePropActionComponent):
            stage_interative_prop_comp: InteractivePropActionComponent = stage_entity.get(InteractivePropActionComponent)
            stage_interative_props: str = stage_interative_prop_comp.interactive_props
            interactive_props: list[str] = parse_complex_interactive_props(stage_interative_props)
            if propname == interactive_props[0]:
                return interactive_props[1]

        return None

        
###################################################################################################################
    def after_use_prop_success(self, entity: Entity, use_prop_result_data: List[tuple[str, str]]) -> None:
        self.add_check_status_action(entity)
        self.imme_add_prison_break_action(entity, use_prop_result_data)
###################################################################################################################
    def add_check_status_action(self, entity: Entity) -> None:
        if entity.has(CheckStatusActionComponent):
            return
        npccomp: NPCComponent = entity.get(NPCComponent)
        action = ActorAction(npccomp.name, CheckStatusActionComponent.__name__, [npccomp.name])
        entity.add(CheckStatusActionComponent, action)
###################################################################################################################
    def imme_add_prison_break_action(self, entity: Entity, use_prop_result_data: List[tuple[str, str]]) -> None:
        
        if len(use_prop_result_data) == 0:
            return
        
        for targetname, propname in use_prop_result_data:

            stage_entity: Optional[Entity] = self.context.getstage(targetname)
            if stage_entity is None:
                continue

            if not stage_entity.has(ExitOfPrisonComponent):
                continue
            
            # 取出数据，并准备沿用LeaveForActionComponent
            conncectstagecomp: ExitOfPrisonComponent = stage_entity.get(ExitOfPrisonComponent)
            connect_stage_entity = self.context.getstage(conncectstagecomp.name)
            if connect_stage_entity is None:
                #assert False, f"{conncectstagecomp.name} is None"
                continue

            if entity.has(PrisonBreakActionComponent):
                entity.remove(PrisonBreakActionComponent)
            
            # 生成离开当前场景的动作
            npccomp: NPCComponent = entity.get(NPCComponent)
            action = ActorAction(npccomp.name, PrisonBreakActionComponent.__name__, [npccomp.current_stage])
            entity.add(PrisonBreakActionComponent, action)

            # 必须跳出循环，因为只能离开一个场景
            break
        

###################################################################################################################