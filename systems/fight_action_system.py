
from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity # type: ignore
from auxiliary.components import FightActionComponent, NPCComponent, StageComponent, SimpleRPGRoleComponent, DeadActionComponent
from auxiliary.extended_context import ExtendedContext
from auxiliary.actor_action import ActorAction
from auxiliary.actor_agent import ActorAgent
from auxiliary.prompt_maker import kill_someone, attack_someone
from typing import Optional
from loguru import logger

class FightActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(FightActionComponent): GroupEvent.ADDED}

    def filter(self, entity: Entity) -> bool:
        return entity.has(FightActionComponent)

    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  FightActionSystem  >>>>>>>>>>>>>>>>>")
        ## 核心处理
        for entity in entities:
            self.handlefight(entity)

        ### 必须删除！！！！！！！！！！！！！！！！！！！！！！！！！！
        for entity in entities:
            entity.remove(FightActionComponent)
        
    def handlefight(self, entity: Entity) -> None:
        comp: FightActionComponent = entity.get(FightActionComponent)
        logger.info(f"FightActionSystem: {comp.action}")
        action: ActorAction = comp.action
        #stage: StageComponent = self.context.get_stagecomponent_by_uncertain_entity(entity)

        attacker: Optional[Entity] = self.context.get_entity_by_name(action.name)
        if attacker is None:
            logger.warning(f"攻击者{action.name}本次攻击出现错误,原因是attacker对象为None,本次攻击无效.")
            return
        for value in action.values:
            attacked: Optional[Entity] = self.context.getnpc(value)
            if attacked is None:
                logger.warning(f"攻击者{action.name}本次攻击出现错误,原因是attacked对象为None,本次攻击无效.")
                return
            if attacker.has(SimpleRPGRoleComponent) and attacked.has(SimpleRPGRoleComponent):
                attacker_comp: SimpleRPGRoleComponent = attacker.get(SimpleRPGRoleComponent)
                attacked_comp: SimpleRPGRoleComponent = attacked.get(SimpleRPGRoleComponent)
                attack_result = attacked_comp.hp - attacker_comp.attack
                attacked.replace(SimpleRPGRoleComponent,attacked_comp.name,100,attack_result,20,"")
                if attack_result <= 0:
                    attacked.add(DeadActionComponent, action)
                    self.context.add_content_to_director_script_by_entity(attacker, kill_someone(action.name, value))
                else:
                    self.context.add_content_to_director_script_by_entity(attacker, attack_someone(action.name, value, attacker_comp.attack, attacked_comp.hp, attacked_comp.maxhp))
            else:
                logger.warning("attacker or attacked has no simple rpg role comp.")
       