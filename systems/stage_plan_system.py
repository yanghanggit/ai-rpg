
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.components import (StageComponent, 
                        FightActionComponent, 
                        SpeakActionComponent,
                        TagActionComponent,
                        MindVoiceActionComponent,
                        RememberActionComponent,
                        BroadcastActionComponent,
                        WhisperActionComponent)
from auxiliary.actor_action import ActorPlan
from auxiliary.prompt_maker import stage_plan_prompt
from auxiliary.extended_context import ExtendedContext
      
class StagePlanSystem(ExecuteProcessor):
    """
    The StagePlanSystem class is responsible for handling stage plans in the game.

    Attributes:
        context: The context object used to access entities and components.

    Methods:
        execute: Executes the StagePlanSystem and handles stage plans.
        handle: Handles a single stage plan entity.
    """

    def __init__(self, context: ExtendedContext) -> None:
        """
        Initializes a new instance of the StagePlanSystem class.

        Args:
            context: The context object used to access entities and components.
        """
        self.context = context

    def execute(self) -> None:
        """
        Executes the StagePlanSystem and handles stage plans.
        """
        print("<<<<<<<<<<<<<  StagePlanSystem  >>>>>>>>>>>>>>>>>")
        entities = self.context.get_group(Matcher(StageComponent)).entities
        for entity in entities:
            self.handle(entity)

    def handle(self, entity: Entity) -> None:
        """
        Handles a single stage plan entity.

        Args:
            entity: The entity representing a stage plan.
        """
        prompt = stage_plan_prompt(entity, self.context)
        ##
        comp = entity.get(StageComponent)
        ##
        try:
            response = comp.agent.request(prompt)
            actorplan = ActorPlan(comp.name, response)
            for action in actorplan.actions:
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

                    case "RememberActionComponent":
                        #print(f"RememberActionComponent: {action.values}")
                        pass

                    case "MindVoiceActionComponent":
                        if not entity.has(MindVoiceActionComponent):
                            entity.add(MindVoiceActionComponent, action)

                    case "BroadcastActionComponent":
                        if not entity.has(BroadcastActionComponent):
                            entity.add(BroadcastActionComponent, action)

                    case "WhisperActionComponent":
                        if not entity.has(WhisperActionComponent):
                            entity.add(WhisperActionComponent, action)
                             
                    case _:
                        print(f"error {action.actionname}, action value {action.values}")
                        continue

        except Exception as e:
            print(f"StagePlanSystem: {e}")  
            return
        return