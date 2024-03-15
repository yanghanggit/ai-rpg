

from entitas import Entity, Matcher, ExecuteProcessor
from components import (NPCComponent, 
                        FightActionComponent, 
                        SpeakActionComponent, 
                        LeaveActionComponent, 
                        TagActionComponent, 
                        HumanInterferenceComponent,
                        MindVoiceActionComponent,
                        BroadcastActionComponent)
from actor_action import ActorPlan
from prompt_maker import npc_plan_prompt
from extended_context import ExtendedContext

class NPCPlanSystem(ExecuteProcessor):
    """
    This class represents a system for handling NPC plans.

    Attributes:
    - context: The context in which the system operates.

    Methods:
    - __init__(self, context): Initializes the NPCPlanSystem object.
    - execute(self): Executes the NPC plan system.
    - handle(self, entity): Handles the plan for a specific NPC entity.
    """

    def __init__(self, context: ExtendedContext) -> None:
        """
        Initializes the NPCPlanSystem object.

        Parameters:
        - context: The context in which the system operates.
        """
        self.context = context

    def execute(self) -> None:
        """
        Executes the NPC plan system.
        """
        print("<<<<<<<<<<<<<  NPCPlanSystem  >>>>>>>>>>>>>>>>>")
        entities = self.context.get_group(Matcher(NPCComponent)).entities
        for entity in entities:
            if entity.has(HumanInterferenceComponent):
                entity.remove(HumanInterferenceComponent)
                print(f"{entity.get(NPCComponent).name}本轮行为计划被人类接管。\n")
                continue

            #开始处理NPC的行为计划
            self.handle(entity)

    def handle(self, entity: Entity) -> None:
        """
        Handles the plan for a specific NPC entity.

        Parameters:
        - entity: The NPC entity to handle the plan for.
        """
        prompt = npc_plan_prompt(entity, self.context)
        comp = entity.get(NPCComponent)
        try:
            response = comp.agent.request(prompt)
            actorplan = ActorPlan(comp.name, response)
            for action in actorplan.actions:
                if len(action.values) == 0:
                    continue
                match action.actionname:
                    case "FightActionComponent":
                        if not entity.has(FightActionComponent):
                            entity.add(FightActionComponent, action)

                    case "LeaveActionComponent":
                        if not entity.has(LeaveActionComponent):
                            entity.add(LeaveActionComponent, action)

                    case "SpeakActionComponent":
                        if not entity.has(SpeakActionComponent):
                            entity.add(SpeakActionComponent, action)
                    
                    case "TagActionComponent":
                        if not entity.has(TagActionComponent):
                            entity.add(TagActionComponent, action)
                    
                    case "RememberActionComponent":
                        print(f"RememberActionComponent: {action.values}")
                        pass

                    case "MindVoiceActionComponent":
                        if not entity.has(MindVoiceActionComponent):
                            entity.add(MindVoiceActionComponent, action)

                    case "BroadcastActionComponent":
                        if not entity.has(BroadcastActionComponent):
                            entity.add(BroadcastActionComponent, action)
                            
                    case _:
                        print(f" {action.actionname}, Unknown action name")
                        continue

        except Exception as e:
            print(f"NPCPlanSystem: {e}")  
            return
        return
