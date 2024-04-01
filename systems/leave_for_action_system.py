
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import (LeaveForActionComponent, 
                        NPCComponent, 
                        StageComponent, 
                        SimpleRPGRoleComponent,
                        BackpackComponent,
                        StageEntryConditionComponent,
                        StageExitConditionComponent,
                        DirectorComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from auxiliary.print_in_color import Color
from auxiliary.prompt_maker import fail_to_enter_stage, fail_to_exit_stage, npc_enter_stage, npc_leave_for_stage
from loguru import logger
from director import Director, LeaveForStageEvent, EnterStageEvent, FailEnterStageEvent, FailExitStageEvent

class NpcBackpackComponentHandle:

    def __init__(self, context: ExtendedContext, npc_entity: Entity) -> None:
        self.context = context
        self.backpack_comp: BackpackComponent = npc_entity.get(BackpackComponent)
        self.backpack_comp_content: set[str] = self.context.file_system.get_backpack_contents(self.backpack_comp)


###集中写一下方便处理，不然每次还要再搜，很麻烦
class LeaveHandle:

    def __init__(self, context: ExtendedContext, who_wana_leave: Entity, target_stage_name: str) -> None:
        self.context = context
        self.who_wana_leave = who_wana_leave
        self.current_stage_name = who_wana_leave.get(NPCComponent).current_stage
        self.current_stage = self.context.getstage(self.current_stage_name)
        self.target_stage_name = target_stage_name
        self.target_stage = self.context.getstage(target_stage_name)



###############################################################################################################################################
class LeaveForActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(LeaveForActionComponent): GroupEvent.ADDED}

    def filter(self, entity: Entity) -> bool:
        return entity.has(LeaveForActionComponent)

    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  LeaveForActionSystem  >>>>>>>>>>>>>>>>>")
        self.handle(entities)

        #必须移除！！！！！
        for entity in entities:
            entity.remove(LeaveForActionComponent)    

    ###############################################################################################################################################
    def handle(self, entities: list[Entity]) -> None:

        for entity in entities:
            if not entity.has(NPCComponent):
                logger.warning(f"LeaveForActionSystem: {entity} is not NPC?!")
                continue
            
            leavecomp: LeaveForActionComponent = entity.get(LeaveForActionComponent)
            action: ActorAction = leavecomp.action
            if len(action.values) == 0:
               logger.warning("没有目标？！")
               continue
            
            #组织一下数据
            logger.debug(f"LeaveForActionSystem: {action}")
            stagename = action.values[0]
            handle = LeaveHandle(self.context, entity, stagename)
            
            #开始使用，简化代码
            if handle.target_stage is None:
                logger.warning(f"{entity.get(NPCComponent).name}想要去往的场景是不存在的: {stagename} 不用往下进行了")
                continue

            if handle.current_stage is None:
                logger.warning(f"{Color.WARNING}{entity.get(NPCComponent).name}当前没有场景,异常情况请检查配置。{Color.ENDC}") 
                continue

            if handle.target_stage == handle.current_stage:
                logger.info(f"{entity.get(NPCComponent).name}想要去往的场景是当前的场景{handle.current_stage_name}: {stagename} 不用往下进行了")
                continue

            if not self.check_current_stage_meets_conditions_for_leaving(handle):
                logger.info(f"{entity.get(NPCComponent).name}当前场景{handle.current_stage_name}不满足离开条件，不能离开")
                continue

            if not self.check_conditions_for_entering_target_stage(handle):
                logger.info(f"{entity.get(NPCComponent).name}目标场景{handle.target_stage_name}不满足进入条件，不能进入")
                continue
            
            ##开始行动了，到了这里就不能终止，前面都是检查。。。。。。。。。。。。。。。。。。。。。。。。。。。。。。。。。。。。。。。。
            if handle.current_stage is not None:
                self.leave_stage(handle)
            else:
                logger.warning(f"当前没有场景, 可能是凭空创建一个player（NPC）") 

            ###核心代码进入一个场景
            self.enter_stage(handle)
    
    ###############################################################################################################################################            
    #当前没有场景, 可能是凭空创建一个player（NPC）
    def enter_stage(self, handle: LeaveHandle) -> None:
        """
        Enters a new stage for the entity.
        """
        ####
        entity = handle.who_wana_leave
        current_stage_name = handle.current_stage_name

        target_stage_name = handle.target_stage_name
        target_stage_entity = handle.target_stage
        npccomp = entity.get(NPCComponent)

        #当前没有场景, 可能是凭空创建一个player（NPC）
        replace_name = npccomp.name
        replace_agent = npccomp.agent
        replace_current_stage = target_stage_name
        entity.replace(NPCComponent, replace_name, replace_agent, replace_current_stage)

        ##
        if target_stage_entity is None:
            logger.warning(f"{Color.WARNING}target_stage_entitiy is None，请检查配置。{Color.ENDC}")
            return
        #target_stage_comp = target_stage_entity.get(StageComponent)
        if current_stage_name != "":
            self.context.add_content_to_director_script_by_entity(target_stage_entity, npc_leave_for_stage(npccomp.name, current_stage_name, target_stage_name))
            self.add_leave_for_stage_event_director(target_stage_entity, npccomp.name, current_stage_name, target_stage_name)
            logger.info(f"{Color.GREEN}{npccomp.name} 离开了{current_stage_name}去了{target_stage_name}.{Color.ENDC}")
        else:
            self.context.add_content_to_director_script_by_entity(target_stage_entity, npc_enter_stage(npccomp.name, target_stage_name))
            self.add_enter_stage_event_director(target_stage_entity, npccomp.name, target_stage_name)
            logger.info(f"{Color.GREEN}{npccomp.name} 进入了{target_stage_name}.{Color.ENDC}")
        
        ##
        # if entity.has(SimpleRPGRoleComponent):
        #     desc = entity.get(SimpleRPGRoleComponent).desc
        #     if desc != "":
        #         target_stage_comp.directorscripts.append(f"{npccomp.name}的描述：{desc}")

    ###############################################################################################################################################
    def leave_stage(self, handle: LeaveHandle) -> None:
        """
        Leaves the current stage for the entity.
        """
        #当前有场景
        entity: Entity = handle.who_wana_leave
        npccomp: NPCComponent = entity.get(NPCComponent)
        if handle.current_stage is None:
            logger.warning(f"{Color.WARNING}current_stage is None，请检查配置。{Color.ENDC}")
            return
        current_stage: Entity = handle.current_stage
        # cur_stage_comp: StageComponent = current_stage.get(StageComponent)

        #更换数据, 因为是namedtuple 只能用替换手段
        replace_name = npccomp.name
        #replace_agent = npccomp.agent
        replace_current_stage = "" #设置空！！！！！
        entity.replace(NPCComponent, replace_name, replace_current_stage)

        #给当前场景添加剧本，如果本次有导演就合进事件
        # cur_stage_comp.directorscripts.append(f"{npccomp.name} 离开{handle.current_stage_name}去了{handle.target_stage_name}")
        self.context.add_content_to_director_script_by_entity(current_stage, npc_leave_for_stage(npccomp.name, handle.current_stage_name, handle.target_stage_name))
        self.add_leave_for_stage_event_director(current_stage, npccomp.name, handle.current_stage_name, handle.target_stage_name)

    ###############################################################################################################################################
    def check_current_stage_meets_conditions_for_leaving(self, handle: LeaveHandle) -> bool:
        if handle.current_stage is None:
            logger.warning(f"{Color.WARNING}handle.current_stage is None，请检查配置。{Color.ENDC}")
            return False
        # 先检查当前场景的离开条件
        if not handle.current_stage.has(StageExitConditionComponent):
            # 如果没有离开条件，直接返回True
            return True
        
        #有检查条件
        exit_condition_comp: StageExitConditionComponent = handle.current_stage.get(StageExitConditionComponent)
        search_list: str = ""
        for condition in exit_condition_comp.conditions:
            if condition in self.context.file_system.get_backpack_contents(handle.who_wana_leave.get(BackpackComponent)):
                #如果满足就放行
                return True
            else:
                search_list += f"'{condition}' "

        logger.info(f"{Color.WARNING}{handle.who_wana_leave.get(NPCComponent).name}背包中没有{search_list}，不能离开{handle.current_stage_name}.{Color.ENDC}")
        self.context.add_content_to_director_script_by_entity(handle.who_wana_leave, fail_to_exit_stage(handle.who_wana_leave.get(NPCComponent).name, handle.current_stage_name, search_list))
        self.add_fail_exit_stage_event_director(handle.current_stage, handle.who_wana_leave.get(NPCComponent).name, handle.current_stage_name, search_list)
        return False
    ###############################################################################################################################################
    def check_conditions_for_entering_target_stage(self, handle: LeaveHandle) -> bool:
        if handle.target_stage is None:
            logger.warning(f"{Color.WARNING}handle.target_stage is None，请检查配置。{Color.ENDC}")
            return False
        
        if not handle.target_stage.has(StageEntryConditionComponent):
            return True
        
        entry_condition_comp: StageEntryConditionComponent = handle.target_stage.get(StageEntryConditionComponent)
        search_list: str = ""
        for condition in entry_condition_comp.conditions:
            if condition in self.context.file_system.get_backpack_contents(handle.who_wana_leave.get(BackpackComponent)):
                return True
            else:
                search_list += f"'{condition}' "
        
        logger.info(f"{Color.WARNING}{handle.who_wana_leave.get(NPCComponent).name}背包中没有{search_list}，不能进入{handle.target_stage_name}.{Color.ENDC}")
        self.context.add_content_to_director_script_by_entity(handle.who_wana_leave, fail_to_enter_stage(handle.who_wana_leave.get(NPCComponent).name, handle.target_stage_name, search_list))
        
        ##重构的        
        if handle.current_stage is not None:
            self.add_fail_enter_stage_event_director(handle.current_stage, handle.who_wana_leave.get(NPCComponent).name, handle.target_stage_name, search_list)
        return False
    
    ###############################################################################################################################################
    def add_leave_for_stage_event_director(self, stageentity: Entity, npcname: str, cur_stage_name: str, target_stage_name: str) -> None:
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        # ##添加导演事件
        directorcomp = stageentity.get(DirectorComponent)
        director: Director = directorcomp.director
        leaveforstageevent = LeaveForStageEvent(npcname, cur_stage_name, target_stage_name)
        director.addevent(leaveforstageevent)
    ###############################################################################################################################################
    def add_enter_stage_event_director(self, stageentity: Entity, npcname: str, target_stage_name: str) -> None:
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        # ##添加导演事件
        directorcomp = stageentity.get(DirectorComponent)
        director: Director = directorcomp.director
        enterstageevent = EnterStageEvent(npcname, target_stage_name)
        director.addevent(enterstageevent)
    ###############################################################################################################################################
    def add_fail_enter_stage_event_director(self, stageentity: Entity, npcname: str, target_stage_name: str, search_list: str) -> None:
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        # ##添加导演事件
        directorcomp = stageentity.get(DirectorComponent)
        director: Director = directorcomp.director
        failevent = FailEnterStageEvent(npcname, target_stage_name, search_list)
        director.addevent(failevent)
    ###############################################################################################################################################
    def add_fail_exit_stage_event_director(self, stageentity: Entity, npcname: str, cur_stage_name: str, search_list: str) -> None:
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        # ##添加导演事件
        directorcomp = stageentity.get(DirectorComponent)
        director: Director = directorcomp.director
        failevent = FailExitStageEvent(npcname, cur_stage_name, search_list)
        director.addevent(failevent)
    ###############################################################################################################################################
