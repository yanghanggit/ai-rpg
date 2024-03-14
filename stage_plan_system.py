
from entitas import Entity, Matcher, ExecuteProcessor
from components import StageComponent, FightActionComponent, SpeakActionComponent, TagActionComponent
from actor_action import ActorPlan
from prompt_maker import stage_plan_prompt

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################       
class StagePlanSystem(ExecuteProcessor):
    
    def __init__(self, context) -> None:
        self.context = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  StagePlanSystem  >>>>>>>>>>>>>>>>>")
        entities = self.context.get_group(Matcher(StageComponent)).entities
        for entity in entities:
            self.handle(entity)

    def handle(self, entity: Entity) -> None:
        prompt = stage_plan_prompt(entity, self.context)
        ##
        comp = entity.get(StageComponent)
        ##
        try:
            response = comp.agent.request(prompt)
            actorplan = ActorPlan(comp.name, response)
            for action in actorplan.actions:
                #print(action)
                if len(action.values) == 0:
                    continue
                # if action.actionname == "FightActionComponent":
                #     if not entity.has(FightActionComponent):
                #         entity.add(FightActionComponent, action)
                # elif action.actionname == "SpeakActionComponent":
                #     if not entity.has(SpeakActionComponent):
                #         entity.add(SpeakActionComponent, action)
                # elif action.actionname == "TagActionComponent":
                #     if not entity.has(TagActionComponent):
                #         entity.add(TagActionComponent, action)
                # else:
                #     print(f"error {action.actionname}, action value {action.values}")
                #     continue
                match action.actionname:
                    case "FightActionComponent":
                        if not entity.has(FightActionComponent):
                            entity.add(FightActionComponent, action)
                    case "SpeakActionComponent":
                        if not entity.has(SpeakActionComponent):
                            entity.add(SpeakActionComponent, action)
                    case "TagActionComponent":
                        if not entity.has(TagActionComponent):
                            entity.add(TagActionComponent, action)
                    case _:
                        print(f"error {action.actionname}, action value {action.values}")
                        continue


        except Exception as e:
            print(f"stage_plan error = {e}")
            return
        return