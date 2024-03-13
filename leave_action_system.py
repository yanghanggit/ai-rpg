
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent
from components import LeaveActionComponent, NPCComponent, StageComponent, PlayerComponent, SimpleRPGRoleComponent
from actor_action import ActorAction
from extended_context import ExtendedContext


###集中写一下方便处理，不然每次还要再搜，很麻烦
class LeaveHandle:

    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
        self.who_wana_leave: Entity = None

        self.current_stage_name: str = ""
        self.current_stage: Entity = None

        self.target_stage_name: str = ""
        self.target_stage: Entity = None

    def init(self, who_wana_leave: Entity, target_stage_name: str) -> bool:
        #
        self.who_wana_leave = who_wana_leave
        self.current_stage_name = who_wana_leave.get(NPCComponent).current_stage
        self.current_stage = self.context.getstage(self.current_stage_name)
        #
        self.target_stage_name = target_stage_name
        self.target_stage = self.context.getstage(target_stage_name)
        return True


###############################################################################################################################################
class LeaveActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(LeaveActionComponent): GroupEvent.ADDED}

    def filter(self, entity: list[Entity]):
        return entity.has(LeaveActionComponent)

    def react(self, entities: list[Entity]):
        print("<<<<<<<<<<<<<  LeaveActionSystem  >>>>>>>>>>>>>>>>>")
        self.handle2(entities)

        #必须移除！！！！！
        for entity in entities:
            entity.remove(LeaveActionComponent)    

    ###############################################################################################################################################
    def handle2(self, entities: list[Entity]) -> None:
        for entity in entities:
            if not entity.has(NPCComponent):
                print(f"LeaveActionSystem: {entity} is not NPC?!")
                continue

            leavecomp: LeaveActionComponent = entity.get(LeaveActionComponent)
            action: ActorAction = leavecomp.action
            if len(action.values) == 0:
               print("没有目标？！")
               continue

            #组织一下数据
            print(f"LeaveActionSystem: {action}")
            stagename = action.values[0]
            handle = LeaveHandle(self.context)
            handle.init(entity, stagename)
            
            #开始使用，简化代码
            if handle.target_stage is None:
                print(f"想要去往的场景是不存在的: {stagename} 不用往下进行了")
                continue

            if handle.target_stage == handle.current_stage:
                print(f"想要去往的场景是当前的场景{handle.current_stage_name}: {stagename} 不用往下进行了")
                continue
            
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
            target_stage_comp.directorscripts.append(f"{npccomp.name} 离开了{current_stage_name} 并进入了场景 {target_stage_name}")
        else:
            target_stage_comp.directorscripts.append(f"{npccomp.name} 进入了场景 {target_stage_name}")
        
        ##
        if entity.has(SimpleRPGRoleComponent):
            desc = entity.get(SimpleRPGRoleComponent).desc
            if desc != "":
                target_stage_comp.directorscripts.append(f"{npccomp.name}的描述：{desc}")

    ###############################################################################################################################################
    def leave_stage(self, handle: LeaveHandle) -> None:
        #当前有场景
        entity: Entity = handle.who_wana_leave
        npccomp: NPCComponent = entity.get(NPCComponent)
        current_stage: Entity = handle.current_stage
        cur_stage_comp: StageComponent = current_stage.get(StageComponent)

        #更换数据, 因为是namedtuple 只能用替换手段
        replace_name = npccomp.name
        replace_agent = npccomp.agent
        replace_current_stage = "" #设置空！！！！！
        entity.replace(NPCComponent, replace_name, replace_agent, replace_current_stage)

        #给当前场景添加剧本，如果本次有导演就合进事件
        cur_stage_comp.directorscripts.append(f"{npccomp.name} 离开了")

    ###############################################################################################################################################
    # def handle(self, entities: list[Entity]) -> None:
    #     return self.handle2(entities)
    #     # 开始处理
    #     for entity in entities:
    #         leavecomp = entity.get(LeaveActionComponent)
    #         action: ActorAction = leavecomp.action
    #         print(f"LeaveActionSystem: {action}")
    #         if len(action.values) == 0:
    #            print(f"LeaveActionSystem: {action.values} is None")
    #            continue
            
    #         target_stage_name = action.values[0]
    #         target_stage_entity = self.context.getstage(target_stage_name)
    #         if target_stage_entity is None:
    #             print(f"LeaveActionSystem: {target_stage_name} is None")
    #             continue

    #         if entity.has(NPCComponent):

    #             npccomp = entity.get(NPCComponent)
    #             current_stage: str = npccomp.current_stage
                
    #             if current_stage != target_stage_name:
    #                 #当前在的场景，准备通知
    #                 cur_stage_entity = self.context.getstage(current_stage)
    #                 if cur_stage_entity is not None:
    #                     #当前有场景
    #                     cur_stage_comp = cur_stage_entity.get(StageComponent)
    #                     #更换数据, 因为是namedtuple 只能用替换手段
    #                     replace_name = npccomp.name
    #                     replace_agent = npccomp.agent
    #                     replace_current_stage = target_stage_name
    #                     entity.replace(NPCComponent, replace_name, replace_agent, replace_current_stage)
    #                     #给当前场景添加记忆
    #                     cur_stage_comp.agent.add_chat_history(f"{npccomp.name} 离开了")
    #                     #给当前场景添加剧本，如果本次有导演就合进事件
    #                     cur_stage_comp.directorscripts.append(f"{npccomp.name} 离开了")
    #                     #自己的记忆更新
    #                     npccomp.agent.add_chat_history(f"你离开了{current_stage}, 去往了{target_stage_name}")
    #                     #新的场景添加记忆
    #                     target_stage_entity.get(StageComponent).agent.add_chat_history(f"{npccomp.name} 进入了场景")
    #                 else :
    #                     #当前没有场景, 可能是凭空创建一个player（NPC）
    #                     replace_name = npccomp.name
    #                     replace_agent = npccomp.agent
    #                     replace_current_stage = target_stage_name
    #                     entity.replace(NPCComponent, replace_name, replace_agent, replace_current_stage)
    #                     #自己的记忆更新
    #                     npccomp.agent.add_chat_history(f"你进入了{target_stage_name}")
    #                     #新的场景添加记忆
    #                     target_stage_entity.get(StageComponent).agent.add_chat_history(f"{npccomp.name} 进入了场景")
    #                     #新的场景添加导演剧本
    #                     target_stage_entity.get(StageComponent).directorscripts.append(f"{npccomp.name} 进入了场景")
    #                     #因为是第一次进入，就必须通知所有已经在场的NPC!
    #                     npcs_in_stage = self.context.get_npcs_in_stage(target_stage_name)
    #                     #测试用，到了这里就是Player
    #                     desc = entity.get(SimpleRPGRoleComponent).desc
    #                     for npc in npcs_in_stage:
    #                         npc_comp = npc.get(NPCComponent)
    #                         if desc != "":
    #                             npc_comp.agent.add_chat_history(f"{npccomp.name} 进入了场景, {desc}")
    #                         else:
    #                             npc_comp.agent.add_chat_history(f"{npccomp.name} 进入了场景")
    #             else:
    #                 print(f"LeaveActionSystem: {npccomp.name} is in {target_stage_name}")

    ###############################################################################################################################################