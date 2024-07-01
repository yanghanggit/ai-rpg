from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity # type: ignore
from ecs_systems.components import AttackActionComponent, SimpleRPGAttrComponent, DeadActionComponent, SimpleRPGWeaponComponent, SimpleRPGArmorComponent
from my_entitas.extended_context import ExtendedContext
from my_agent.agent_action import AgentAction
from loguru import logger
from ecs_systems.stage_director_component import notify_stage_director
from ecs_systems.stage_director_event import IStageDirectorEvent
from typing import cast, override
from gameplay_checks.conversation_check import conversation_check, ErrorConversationEnable
from builtin_prompt.cn_builtin_prompt import kill_prompt, attack_prompt



####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class StageOrActorKillEvent(IStageDirectorEvent):

    """
    事件通知：在Attack之后，直接杀死了某个人。
    """
    
    def __init__(self, attacker: str, target: str) -> None:
        self.attacker: str = attacker
        self.target: str = target

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        event = kill_prompt(self.attacker, self.target)
        return event
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = kill_prompt(self.attacker, self.target)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class StageOrActorAttackEvent(IStageDirectorEvent):

    """
    事件通知：Attack行动的通知
    """

    def __init__(self, attacker: str, target: str, damage: int, curhp: int, maxhp: int) -> None:
        self.attacker: str = attacker
        self.target: str = target
        self.damage: int = damage
        self.curhp: int = curhp
        self.maxhp: int = maxhp

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        event = attack_prompt(self.attacker, self.target, self.damage, self.curhp, self.maxhp)
        return event
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = attack_prompt(self.attacker, self.target, self.damage, self.curhp, self.maxhp)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class AttackActionSystem(ReactiveProcessor):

    """
    处理：AttackActionComponent 的系统
    要求：AttackActionComponent 和 SimpleRPGAttrComponent 必须同时存在，否则无法处理。
    """

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context: ExtendedContext = context
######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(AttackActionComponent): GroupEvent.ADDED}
######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(AttackActionComponent) and entity.has(SimpleRPGAttrComponent)
######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._attack(entity)
 ######################################################################################################################################################  
    # todo 函数太长了，后续可以考虑拆分！！！！！
    def _attack(self, _entity: Entity) -> None:
        context = self.context
        rpgcomp: SimpleRPGAttrComponent = _entity.get(SimpleRPGAttrComponent)
        fightcomp: AttackActionComponent = _entity.get(AttackActionComponent)
        action: AgentAction = fightcomp.action
        for value_as_target_name in action._values:

            _target_entity = context.get_entity_by_code_name_component(value_as_target_name)
            if _target_entity is None:
                logger.warning(f"攻击者{action._actor_name}意图攻击的对象{value_as_target_name}无法被找到,本次攻击无效.")
                continue

            if not _target_entity.has(SimpleRPGAttrComponent):
                logger.warning(f"攻击者{action._actor_name}意图攻击的对象{value_as_target_name}没有SimpleRPGComponent,本次攻击无效.")
                continue

            conversation_check_error = conversation_check(self.context, _entity, value_as_target_name)
            if conversation_check_error != ErrorConversationEnable.VALID:
                if conversation_check_error == ErrorConversationEnable.TARGET_DOES_NOT_EXIST:
                    logger.error(f"攻击者{action._actor_name}意图攻击的对象{value_as_target_name}不存在,本次攻击无效.")
                    # todo 是否应该因该提示发起人？做一下矫正？

                elif conversation_check_error == ErrorConversationEnable.WITHOUT_BEING_IN_STAGE:
                    logger.error(f"攻击者{action._actor_name}不在任何舞台上,本次攻击无效.? 这是一个严重的错误！")
                    assert False # 不要继续了，因为出现了严重的错误

                elif conversation_check_error == ErrorConversationEnable.NOT_IN_THE_SAME_STAGE:

                    # 名字拿出来，看一下
                    assert _entity is not None
                    stage1 = self.context.safe_get_stage_entity(_entity)
                    assert stage1 is not None
                    stage1_name = self.context.safe_get_entity_name(stage1)

                    assert _target_entity is not None
                    stage2 = self.context.safe_get_stage_entity(_target_entity)
                    assert stage2 is not None
                    stage2_name = self.context.safe_get_entity_name(stage2)

                    logger.error(f"攻击者 {action._actor_name}:{stage1_name} 和攻击对象 {value_as_target_name}:{stage2_name} 不在同一个舞台上,本次攻击无效.")

                # 跳过去，不能继续了！
                continue
            
            #目标拿出来
            target_rpg_comp: SimpleRPGAttrComponent = _target_entity.get(SimpleRPGAttrComponent)

            #简单的战斗计算，简单的血减掉伤害
            hp = target_rpg_comp.hp
            damage = self.final_attack_val(_entity) #rpgcomp.attack
            # 必须控制在0和最大值之间
            damage = damage - self.final_defense_val(_target_entity) #targetsrpgcomp.defense
            if damage < 0:
                damage = 0
            
            lefthp = hp - damage
            lefthp = max(0, min(lefthp, target_rpg_comp.maxhp))

            #结果修改
            _target_entity.replace(SimpleRPGAttrComponent, target_rpg_comp.name, target_rpg_comp.maxhp, lefthp, target_rpg_comp.attack, target_rpg_comp.defense)

            ##死亡是关键
            isdead = (lefthp <= 0)

            ## 死后处理大流程，step1——道具怎么办？后续可以封装的复杂一些: 夺取唯一性道具.
            if isdead:  
                self.unique_prop_be_taken_away(_entity, _target_entity)

            ## 可以加一些别的。。。。。。。。。。。。
            ## 比如杀人多了会被世界管理员记住——你是大坏蛋
            ## 。。。。。。。。。。。。。。。。。。。

            ## 死后处理大流程，step最后——死亡组件系统必须要添加
            if isdead:
                if not _target_entity.has(DeadActionComponent):
                    #复制一个，不用以前的，怕GC不掉
                    _target_entity.add(DeadActionComponent, AgentAction(action._actor_name, action._action_name, action._values)) 

            ## 导演系统，单独处理，有旧的代码
            if isdead:
                # 直接打死
                notify_stage_director(context, _entity, StageOrActorKillEvent(rpgcomp.name, value_as_target_name))
            else:
                # 没有打死，就把伤害通知给导演
                notify_stage_director(context, _entity, StageOrActorAttackEvent(rpgcomp.name, value_as_target_name, damage, lefthp, target_rpg_comp.maxhp))
######################################################################################################################################################
    ## 杀死对方就直接夺取唯一性道具。
    def unique_prop_be_taken_away(self, _entity: Entity, _target_entity: Entity) -> None:

        file_system = self.context.file_system
        _rpg_comp: SimpleRPGAttrComponent = _entity.get(SimpleRPGAttrComponent)
        _target_rpg_comp: SimpleRPGAttrComponent = _target_entity.get(SimpleRPGAttrComponent)
        logger.info(f"{_rpg_comp.name} kill => {_target_rpg_comp.name}")
        
        prop_files = file_system.get_prop_files(_target_rpg_comp.name)
        for propfile in prop_files:
            if not propfile._prop.isunique():
                logger.info(f"the propfile {propfile._name} is not unique, so it will not be taken away.")
                continue
            # 交换文件，即交换道具文件即可
            file_system.exchange_prop_file(_target_rpg_comp.name, _rpg_comp.name, propfile._name)        
######################################################################################################################################################
    def final_attack_val(self, entity: Entity) -> int:
        # 最后的攻击力
        final: int = 0

        #基础的伤害
        rpgcomp: SimpleRPGAttrComponent = entity.get(SimpleRPGAttrComponent)
        final += cast(int, rpgcomp.attack)

        #计算武器带来的伤害
        if entity.has(SimpleRPGWeaponComponent):
            weaponcomp: SimpleRPGWeaponComponent = entity.get(SimpleRPGWeaponComponent)
            final += cast(int, weaponcomp.attack)

        return final
######################################################################################################################################################
    def final_defense_val(self, entity: Entity) -> int:
        # 最后的防御力
        final: int = 0

        #基础防御力
        rpgcomp: SimpleRPGAttrComponent = entity.get(SimpleRPGAttrComponent)
        final += cast(int, rpgcomp.defense)

        #计算衣服带来的防御力
        if entity.has(SimpleRPGArmorComponent):
            armorcomp: SimpleRPGArmorComponent = entity.get(SimpleRPGArmorComponent)
            final += cast(int, armorcomp.defense)

        return final
######################################################################################################################################################