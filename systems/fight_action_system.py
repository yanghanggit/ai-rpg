from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity # type: ignore
from auxiliary.components import FightActionComponent, SimpleRPGRoleComponent, DeadActionComponent
from auxiliary.extended_context import ExtendedContext
from auxiliary.actor_action import ActorAction
from auxiliary.prompt_maker import kill_someone, attack_someone
from loguru import logger
from director_component import DirectorComponent
from director_event import KillSomeoneEvent, AttackSomeoneEvent

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
            self.handle(entity)

        ### 必须删除！！！！！！！！！！！！！！！！！！！！！！！！！！
        for entity in entities:
            entity.remove(FightActionComponent)
 ######################################################################################################################################################   
    def handle(self, entity: Entity) -> None:
        rpgcomp: SimpleRPGRoleComponent = entity.get(SimpleRPGRoleComponent)
        if rpgcomp is None:
            logger.warning(f"FightActionSystem: 没有SimpleRPGRoleComponent,本次攻击无效.")
            return

        context = self.context
        fightcomp: FightActionComponent = entity.get(FightActionComponent)
        action: ActorAction = fightcomp.action
        for value in action.values:

            findtarget = context.get_by_code_name_component(value)
            if findtarget is None:
                logger.warning(f"攻击者{action.name}意图攻击的对象{value}无法被找到,本次攻击无效.")
                continue

            if not findtarget.has(SimpleRPGRoleComponent):
                logger.warning(f"攻击者{action.name}意图攻击的对象{value}没有SimpleRPGRoleComponent,本次攻击无效.")
                continue
            
            #目标拿出来
            targetsrpgcomp: SimpleRPGRoleComponent = findtarget.get(SimpleRPGRoleComponent)

            #简单的战斗计算，简单的血减掉伤害
            hp = targetsrpgcomp.hp
            damage = rpgcomp.attack
            # 必须控制在0和最大值之间
            lefthp = hp - damage
            lefthp = max(0, min(lefthp, targetsrpgcomp.maxhp))

            #结果修改
            findtarget.replace(SimpleRPGRoleComponent, targetsrpgcomp.name, targetsrpgcomp.maxhp, lefthp, targetsrpgcomp.attack)

            ##死亡是关键
            isdead = (lefthp <= 0)

            ## 死亡组件系统必须要添加，单独处理，很重要
            if isdead:
                if not findtarget.has(DeadActionComponent):
                    #复制一个，不用以前的，怕GC不掉
                    findtarget.add(DeadActionComponent, ActorAction(action.name, action.actionname, action.values)) 

            ## 导演系统，单独处理，有旧的代码
            if isdead:
                self.context.legacy_add_content_to_director_script_by_entity(entity, kill_someone(action.name, value))
                self.add_kill_someone_event_to_director(entity, value)
            else:
                self.context.legacy_add_content_to_director_script_by_entity(entity, attack_someone(action.name, value, rpgcomp.attack, targetsrpgcomp.hp, targetsrpgcomp.maxhp))
                self.add_attack_someone_event_to_director(entity, value, rpgcomp.attack, targetsrpgcomp.hp, targetsrpgcomp.maxhp)
                
######################################################################################################################################################
    ## 重构事件
    def add_kill_someone_event_to_director(self, entity: Entity, targetname: str) -> None:
        if entity is None or not entity.has(SimpleRPGRoleComponent):
            return
        ##添加导演事件
        stageentity = self.context.get_stage_entity_by_uncertain_entity(entity)
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        #
        rpgcomp: SimpleRPGRoleComponent = entity.get(SimpleRPGRoleComponent)
        rpgname: str = rpgcomp.name
        #
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        killsomeoneevent = KillSomeoneEvent(rpgname, targetname)
        directorcomp.addevent(killsomeoneevent)
######################################################################################################################################################
    ## 重构事件
    def add_attack_someone_event_to_director(self, entity: Entity, targetname: str, damage: int, curhp: int, maxhp: int) -> None:
        if entity is None or not entity.has(SimpleRPGRoleComponent):
            return
        ##添加导演事件
        stageentity = self.context.get_stage_entity_by_uncertain_entity(entity)
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        #
        rpgcomp: SimpleRPGRoleComponent = entity.get(SimpleRPGRoleComponent)
        rpgname: str = rpgcomp.name
        #
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        attacksomeoneevent = AttackSomeoneEvent(rpgname, targetname, damage, curhp, maxhp)
        directorcomp.addevent(attacksomeoneevent)
######################################################################################################################################################
       