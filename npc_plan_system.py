
from entitas import Entity, Matcher, ExecuteProcessor
from components import NPCComponent, FightActionComponent, SpeakActionComponent, LeaveActionComponent
from actor_action import ActorPlan



###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################   
class NPCPlanSystem(ExecuteProcessor):
    
    def __init__(self, context) -> None:
        self.context = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  NPCPlanSystem >>>>>>>>>>>>>>>>>")
        entities = self.context.get_group(Matcher(NPCComponent)).entities
        for entity in entities:
            self.handle(entity)

    def handle(self, entity: Entity) -> None:
        prompt =  f"""
        # 你需要做出计划(你将要做的事)，并以JSON输出结果.（注意！以下规则与限制仅限本次对话生成，结束后回复原有对话规则）

        ## 步骤
        1. 确认自身状态。
        2. 所有角色当前所处的状态和关系。
        3. 思考你下一步的行动。
        4. 基于上述信息，构建你的行动计划。

        ## 输出格式(JSON)
        - 参考格式：{{'action1': ["value1"，“value2”, ...], 'action2': ["value1"，“value2”, ...],.....}}
        - 其中 'action?'是你的"行动类型"（见下文）
        - 其中 "value?" 是你的"行动目标"(可以是一个或多个)
        
        ### 关于action——“行动类型”的逻辑
        - 如果你希望对目标产生敌对行为，比如攻击。则action的值为"FightActionComponent"，value为你本行动针对的目标
        - 如果你有想要说的话或者心里描写。则action的值为"SpeakActionComponent"，value为你想说的话或者心里描写
        - 如果表示想离开当前场景，有可能是逃跑。action的值为"LeaveActionComponent"，value是你想要去往的场景名字（你必须能明确叫出场景的名字），或者你曾经知道的场景名字
        - 如果与你相关的特征标签。则action的值为"TagActionComponent"，value你的特征标签
        - action值不允许出现FightActionComponent，SpeakActionComponent，LeaveActionComponent，TagActionComponent之外的值

        ## 补充约束
        - 不要将JSON输出生这样的格式：```...```
        """

        ##
        comp = entity.get(NPCComponent)
        ##
        try:
            response = comp.agent.request(prompt)
            actorplan = ActorPlan(comp.name, response)
            for action in actorplan.actions:
                #print(action)
                if len(action.values) == 0:
                    continue
                if action.actionname == "FightActionComponent":
                    if not entity.has(FightActionComponent):
                        entity.add(FightActionComponent, action)
                elif action.actionname == "LeaveActionComponent":
                    if not entity.has(LeaveActionComponent):
                        entity.add(LeaveActionComponent, action)
                elif action.actionname == "SpeakActionComponent":
                    if not entity.has(SpeakActionComponent):
                        entity.add(SpeakActionComponent, action)
                elif action.actionname == "TagActionComponent":
                    pass
                    #print(f"TagActionComponent, action value = {action.values}")
                else:
                    print(f" {action.actionname}, Unknown action name")

        except Exception as e:
            print(f"stage_plan error = {e}")
            return
        return    