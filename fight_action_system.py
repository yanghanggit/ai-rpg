
from entitas import Matcher, ReactiveProcessor, GroupEvent
from components import FightActionComponent, NPCComponent, StageComponent
from extended_context import ExtendedContext
from actor_action import ActorAction
from actor_agent import ActorAgent

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################    
class FightActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(FightActionComponent): GroupEvent.ADDED}

    def filter(self, entity):
        return entity.has(FightActionComponent)

    def react(self, entities):
        print("<<<<<<<<<<<<<  FightActionSystem >>>>>>>>>>>>>>>>>")
        for entity in entities:
            self.handlememory(entity)
            self.handlefight(entity)
            entity.remove(FightActionComponent)         

    ###############################################################################################################################################
    def handlememory(self, entity) -> None:
        comp = entity.get(FightActionComponent)
        print(f"FightActionSystem: {comp.action}")

        action: ActorAction = comp.action
        entity = self.context.getnpc(action.name)
        if entity is not None:
            npccomp = entity.get(NPCComponent) 
            agent: ActorAgent = npccomp.agent
            alltargets = "\n".join(action.values)
            agent.add_chat_history(f"你向{alltargets}发起了攻击")
            return
        
        entity = self.context.getstage(action.name)
        if entity is not None:
            npccomp = entity.get(StageComponent) 
            agent: ActorAgent = npccomp.agent
            alltargets = "\n".join(action.values)
            agent.add_chat_history(f"你向{alltargets}发起了攻击")
            return
        
    ###############################################################################################################################################
    def handlefight(self, entity) -> None:
        comp = entity.get(FightActionComponent)
        print(f"FightActionSystem: {comp.action}")
       