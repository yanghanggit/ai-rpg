
from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity
from components import FightActionComponent, NPCComponent, StageComponent, SimpleRPGRoleComponent, DeadActionComponent
from extended_context import ExtendedContext
from actor_action import ActorAction
from actor_agent import ActorAgent

class FightActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(FightActionComponent): GroupEvent.ADDED}

    def filter(self, entity):
        return entity.has(FightActionComponent)

    def react(self, entities):
        print("<<<<<<<<<<<<<  FightActionSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            #self.handlememory(entity)
            self.handlefight(entity)

        ### 必须删除！！！！！！！！！！！！！！！！！！！！！！！！！！
        for entity in entities:
            entity.remove(FightActionComponent)

    # def handlememory(self, entity) -> None:
    #     comp = entity.get(FightActionComponent)
    #     print(f"FightActionSystem: {comp.action}")

    #     action: ActorAction = comp.action
    #     entity = self.context.getnpc(action.name)
    #     if entity is not None:
    #         npccomp: NPCComponent = entity.get(NPCComponent) 
    #         agent: ActorAgent = npccomp.agent
    #         alltargets = "\n".join(action.values)
    #         agent.add_chat_history(f"你向{alltargets}发起了攻击")
    #         print(f"{npccomp.name}向{alltargets}发动了attack.")
    #         return
        
    #     entity = self.context.getstage(action.name)
    #     if entity is not None:
    #         npccomp = entity.get(StageComponent) 
    #         agent: ActorAgent = npccomp.agent
    #         alltargets = "\n".join(action.values)
    #         agent.add_chat_history(f"你向{alltargets}发起了攻击")
    #         print(f"{npccomp.name}向{alltargets}发动了attack.")
    #         return
        
    def handlefight(self, entity: Entity) -> None:
        comp: FightActionComponent = entity.get(FightActionComponent)
        print(f"FightActionSystem: {comp.action}")
        action: ActorAction = comp.action
        stage: StageComponent = self.context.get_stage_by_entity(entity)

        attacker: Entity = self.context.getnpc(action.name)
        for value in action.values:
            attacked: Entity = self.context.getnpc(value)
            if attacker.has(SimpleRPGRoleComponent) and attacked.has(SimpleRPGRoleComponent):
                attacker_comp: SimpleRPGRoleComponent = attacker.get(SimpleRPGRoleComponent)
                attacked_comp: SimpleRPGRoleComponent = attacked.get(SimpleRPGRoleComponent)
                attack_result = attacked_comp.hp - attacker_comp.attack
                attacked.replace(SimpleRPGRoleComponent,attacked_comp.name,100,attack_result,60,"")
                if attack_result <= 0:
                    attacked.add(DeadActionComponent, action)
                    fight = f"{action.name}对{value}发动了一次攻击,造成了{value}死亡。"
                    stage.directorscripts.append(fight)
                else:
                    fight = f"{action.name}对{value}发动了一次攻击,但是没有能造成{value}死亡,{value}血量剩余{attack_result}%."
                    stage.directorscripts.append(fight)
            else:
                print("attacker or attacked has no simple rpg role comp.")
       