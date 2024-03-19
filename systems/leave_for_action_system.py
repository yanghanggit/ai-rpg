"""
This module contains the implementation of the LeaveForActionSystem class, which is responsible for handling the leave action of entities in a game.

The LeaveForActionSystem class is a subclass of the ReactiveProcessor class and is used to react to entities that have the LeaveForActionComponent added to them.

Classes:
- LeaveForActionSystem: A class that handles the leave action of entities in a game.

Methods:
- __init__(self, context: ExtendedContext): Initializes a new instance of the LeaveForActionSystem class.
- get_trigger(self): Returns the trigger for the system, which is the LeaveForActionComponent added to entities.
- filter(self, entity: list[Entity]): Filters the entities based on the presence of the LeaveForActionComponent.
- react(self, entities: list[Entity]): Reacts to the entities by handling the leave action.
- handle2(self, entities: list[Entity]) -> None: Handles the leave action for the entities.
- enter_stage(self, handle: LeaveHandle) -> None: Handles the entering of a new stage for the entity.
- leave_stage(self, handle: LeaveHandle) -> None: Handles the leaving of the current stage for the entity.
"""

from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import (LeaveForActionComponent, 
                        NPCComponent, 
                        StageComponent, 
                        SimpleRPGRoleComponent,
                        BackpackComponent,
                        StageEntryConditionComponent,
                        StageExitConditionComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from agents.tools.print_in_color import Color
from auxiliary.prompt_maker import fail_to_enter_stage, fail_to_exit_stage, npc_enter_stage, npc_leave_for_stage
from typing import Optional

class NpcBackpackComponentHandle:
    """
    Class representing the NPC handling system.

    Attributes:
    - context (ExtendedContext): The extended context object.
    - backpack_comp (BackpackComponent): The backpack component of the NPC.
    - backpack_comp_content (set[str]): The content of the backpack component.
    """

    def __init__(self, context: ExtendedContext, npc_entity: Entity) -> None:
        """
        Initializes a new instance of the NpcHandle class.

        Parameters:
        - context (ExtendedContext): The extended context object.
        """
        self.context = context
        self.backpack_comp: BackpackComponent = npc_entity.get(BackpackComponent)
        self.backpack_comp_content: set[str] = set(self.backpack_comp.name_items)

    # def init(self, npc_entity: Entity) -> bool:
    #     """
    #     Initializes the NPC handling system.

    #     Parameters:
    #     - npc_entity (Entity): The NPC entity.

    #     Returns:
    #     - bool: True if initialization is successful, False otherwise.
    #     """
    #     self.backpack_comp: BackpackComponent = npc_entity.get(BackpackComponent)
    #     self.backpack_comp_content = set(self.backpack_comp.name_items)
    #     return True

###集中写一下方便处理，不然每次还要再搜，很麻烦
class LeaveHandle:
    """
    Class representing the leave handling system.

    Attributes:
    - context (ExtendedContext): The extended context object.
    - who_wana_leave (Entity): The entity that wants to leave.
    - current_stage_name (str): The name of the current stage.
    - current_stage (Entity): The current stage entity.
    - target_stage_name (str): The name of the target stage.
    - target_stage (Entity): The target stage entity.
    """

    def __init__(self, context: ExtendedContext, who_wana_leave: Entity, target_stage_name: str) -> None:
        """
        Initializes a new instance of the LeaveHandle class.

        Parameters:
        - context (ExtendedContext): The extended context object.
        """
        self.context = context
        self.who_wana_leave = who_wana_leave
        self.current_stage_name = who_wana_leave.get(NPCComponent).current_stage
        self.current_stage = self.context.getstage(self.current_stage_name)
        self.target_stage_name = target_stage_name
        self.target_stage = self.context.getstage(target_stage_name)

    # def init(self, who_wana_leave: Entity, target_stage_name: str) -> bool:
    #     """
    #     Initializes the leave handling system.

    #     Parameters:
    #     - who_wana_leave (Entity): The entity that wants to leave.
    #     - target_stage_name (str): The name of the target stage.

    #     Returns:
    #     - bool: True if initialization is successful, False otherwise.
    #     """
    #     self.who_wana_leave = who_wana_leave
    #     self.current_stage_name = who_wana_leave.get(NPCComponent).current_stage
    #     self.current_stage = self.context.getstage(self.current_stage_name)
    #     self.target_stage_name = target_stage_name
    #     self.target_stage = self.context.getstage(target_stage_name)
    #     return True


###############################################################################################################################################
class LeaveForActionSystem(ReactiveProcessor):
    """
    The LeaveForActionSystem is responsible for handling the leave action of entities in the game.
    It reacts to the addition of entities with the LeaveForActionComponent and performs the necessary actions.
    """
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(LeaveForActionComponent): GroupEvent.ADDED}

    def filter(self, entity: Entity) -> bool:
        return entity.has(LeaveForActionComponent)

    def react(self, entities: list[Entity]) -> None:
        """
        Reacts to the addition of entities with the LeaveForActionComponent.
        Performs the necessary actions for leaving the current stage and entering a new stage.
        """
        print("<<<<<<<<<<<<<  LeaveForActionSystem  >>>>>>>>>>>>>>>>>")
        self.handle2(entities)

        #必须移除！！！！！
        for entity in entities:
            entity.remove(LeaveForActionComponent)    

    ###############################################################################################################################################
    def handle2(self, entities: list[Entity]) -> None:
        """
        Handles the leave action for each entity in the given list of entities.
        """
        for entity in entities:
            if not entity.has(NPCComponent):
                print(f"LeaveForActionSystem: {entity} is not NPC?!")
                continue
            
            leavecomp: LeaveForActionComponent = entity.get(LeaveForActionComponent)
            action: ActorAction = leavecomp.action
            if len(action.values) == 0:
               print("没有目标？！")
               continue
            
            #组织一下数据
            print(f"LeaveForActionSystem: {action}")
            stagename = action.values[0]
            handle = LeaveHandle(self.context, entity, stagename)
            #handle.init(entity, stagename)
            
            #开始使用，简化代码
            if handle.target_stage is None:
                print(f"{entity.get(NPCComponent).name}想要去往的场景是不存在的: {stagename} 不用往下进行了")
                continue

            if handle.target_stage == handle.current_stage:
                print(f"{entity.get(NPCComponent).name}想要去往的场景是当前的场景{handle.current_stage_name}: {stagename} 不用往下进行了")
                continue

            # 判断当前场景的离开条件和目标场景的进入条件
            if handle.current_stage.has(StageExitConditionComponent) or handle.target_stage.has(StageEntryConditionComponent):
                #先处理npc的背包内容
                npc_handle = NpcBackpackComponentHandle(self.context, entity)
                #npc_handle.init(entity)
                # 先检查当前场景的离开条件
                if handle.current_stage.has(StageExitConditionComponent):
                    exit_condition_comp: StageExitConditionComponent = handle.current_stage.get(StageExitConditionComponent)
                    for condition in exit_condition_comp.conditions:
                        if condition not in npc_handle.backpack_comp_content:
                            print(f"{Color.WARNING}{entity.get(NPCComponent).name}背包中没有{condition}，不能离开{handle.current_stage_name}.{Color.ENDC}")
                            self.context.add_content_to_director_script_by_entity(entity, fail_to_exit_stage(entity.get(NPCComponent).name, handle.current_stage_name, condition))
                            return
                # 再检查目标场景的进入条件  
                if handle.target_stage.has(StageEntryConditionComponent):
                    entry_condition_comp: StageEntryConditionComponent = handle.target_stage.get(StageEntryConditionComponent)
                    for condition in entry_condition_comp.conditions:
                        if condition not in npc_handle.backpack_comp_content:
                            print(f"{Color.WARNING}{entity.get(NPCComponent).name}背包中没有{condition}，不能进入{handle.target_stage_name}.{Color.ENDC}")
                            self.context.add_content_to_director_script_by_entity(entity, fail_to_enter_stage(entity.get(NPCComponent).name, handle.target_stage_name, condition))
                            return
            
            ##如果当前有场景就要离开
            if handle.current_stage is not None:
                self.leave_stage(handle)
            else:
                print(f"当前没有场景, 可能是凭空创建一个player（NPC）") 

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
        target_stage_comp = target_stage_entity.get(StageComponent)
        if current_stage_name != "":
            self.context.add_content_to_director_script_by_entity(target_stage_entity, npc_leave_for_stage(npccomp.name, current_stage_name, target_stage_name))
            print(f"{Color.GREEN}{npccomp.name} 离开了{current_stage_name}去了{target_stage_name}.{Color.ENDC}")
        else:
            self.context.add_content_to_director_script_by_entity(target_stage_entity, npc_enter_stage(npccomp.name, target_stage_name))
            print(f"{Color.GREEN}{npccomp.name} 进入了{target_stage_name}.{Color.ENDC}")
        
        ##
        if entity.has(SimpleRPGRoleComponent):
            desc = entity.get(SimpleRPGRoleComponent).desc
            if desc != "":
                target_stage_comp.directorscripts.append(f"{npccomp.name}的描述：{desc}")

    ###############################################################################################################################################
    def leave_stage(self, handle: LeaveHandle) -> None:
        """
        Leaves the current stage for the entity.
        """
        #当前有场景
        entity: Entity = handle.who_wana_leave
        npccomp: NPCComponent = entity.get(NPCComponent)
        current_stage: Entity = handle.current_stage
        # cur_stage_comp: StageComponent = current_stage.get(StageComponent)

        #更换数据, 因为是namedtuple 只能用替换手段
        replace_name = npccomp.name
        replace_agent = npccomp.agent
        replace_current_stage = "" #设置空！！！！！
        entity.replace(NPCComponent, replace_name, replace_agent, replace_current_stage)

        #给当前场景添加剧本，如果本次有导演就合进事件
        # cur_stage_comp.directorscripts.append(f"{npccomp.name} 离开{handle.current_stage_name}去了{handle.target_stage_name}")
        self.context.add_content_to_director_script_by_entity(current_stage, npc_leave_for_stage(npccomp.name, handle.current_stage_name, handle.target_stage_name))

    ###############################################################################################################################################