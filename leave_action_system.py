
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent
from components import LeaveActionComponent, NPCComponent, StageComponent, PlayerComponent, SimpleRPGRoleComponent
from actor_action import ActorAction
from extended_context import ExtendedContext

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
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
        self.handle(entities)

        #必须移除！！！！！
        for entity in entities:
            entity.remove(LeaveActionComponent)    

    ###############################################################################################################################################
    def handle(self, entities: list[Entity]) -> None:
        # 开始处理
        for entity in entities:
            leavecomp = entity.get(LeaveActionComponent)
            action: ActorAction = leavecomp.action
            print(f"LeaveActionSystem: {action}")
            if len(action.values) == 0:
               print(f"LeaveActionSystem: {action.values} is None")
               continue
            
            target_stage_name = action.values[0]
            target_stage_entity = self.context.getstage(target_stage_name)
            if target_stage_entity is None:
                print(f"LeaveActionSystem: {target_stage_name} is None")
                continue

            if entity.has(NPCComponent):

                npccomp = entity.get(NPCComponent)
                current_stage: str = npccomp.current_stage
                
                if current_stage != target_stage_name:
                    #当前在的场景，准备通知
                    cur_stage_entity = self.context.getstage(current_stage)
                    if cur_stage_entity is not None:
                        #当前有场景
                        cur_stage_comp = cur_stage_entity.get(StageComponent)
                        #更换数据, 因为是namedtuple 只能用替换手段
                        replace_name = npccomp.name
                        replace_agent = npccomp.agent
                        replace_current_stage = target_stage_name
                        entity.replace(NPCComponent, replace_name, replace_agent, replace_current_stage)
                        #给当前场景添加记忆
                        cur_stage_comp.agent.add_chat_history(f"{npccomp.name} 离开了")
                        #给当前场景添加剧本，如果本次有导演就合进事件
                        cur_stage_comp.directorscripts.append(f"{npccomp.name} 离开了")
                        #自己的记忆更新
                        npccomp.agent.add_chat_history(f"你离开了{current_stage}, 去往了{target_stage_name}")
                        #新的场景添加记忆
                        target_stage_entity.get(StageComponent).agent.add_chat_history(f"{npccomp.name} 进入了场景")
                    else :
                        #当前没有场景, 可能是凭空创建一个player（NPC）
                        replace_name = npccomp.name
                        replace_agent = npccomp.agent
                        replace_current_stage = target_stage_name
                        entity.replace(NPCComponent, replace_name, replace_agent, replace_current_stage)
                        #自己的记忆更新
                        npccomp.agent.add_chat_history(f"你进入了{target_stage_name}")
                        #新的场景添加记忆
                        target_stage_entity.get(StageComponent).agent.add_chat_history(f"{npccomp.name} 进入了场景")
                        #新的场景添加导演剧本
                        target_stage_entity.get(StageComponent).directorscripts.append(f"{npccomp.name} 进入了场景")
                        #因为是第一次进入，就必须通知所有已经在场的NPC!
                        npcs_in_stage = self.context.get_npcs_in_stage(target_stage_name)
                        #测试用，到了这里就是Player
                        desc = entity.get(SimpleRPGRoleComponent).desc
                        for npc in npcs_in_stage:
                            npc_comp = npc.get(NPCComponent)
                            if desc != "":
                                npc_comp.agent.add_chat_history(f"{npccomp.name} 进入了场景, {desc}")
                            else:
                                npc_comp.agent.add_chat_history(f"{npccomp.name} 进入了场景")
                else:
                    print(f"LeaveActionSystem: {npccomp.name} is in {target_stage_name}")

    ###############################################################################################################################################