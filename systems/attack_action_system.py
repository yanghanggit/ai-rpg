from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity # type: ignore
from auxiliary.components import AttackActionComponent, SimpleRPGRoleComponent, DeadActionComponent, SimpleRPGRoleWeaponComponent, SimpleRPGRoleArmorComponent
from auxiliary.extended_context import ExtendedContext
from auxiliary.actor_action import ActorAction
from loguru import logger
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import NPCKillSomeoneEvent, NPCAttackSomeoneEvent
from typing import cast

class AttackActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
######################################################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(AttackActionComponent): GroupEvent.ADDED}
######################################################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(AttackActionComponent) and entity.has(SimpleRPGRoleComponent)
######################################################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.fight(entity)
 ######################################################################################################################################################   
    def fight(self, entity: Entity) -> None:
        context = self.context
        rpgcomp: SimpleRPGRoleComponent = entity.get(SimpleRPGRoleComponent)
        fightcomp: AttackActionComponent = entity.get(AttackActionComponent)
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
            damage = self.final_attack_val(entity) #rpgcomp.attack
            # 必须控制在0和最大值之间
            damage = damage - self.final_defense_val(findtarget) #targetsrpgcomp.defense
            if damage < 0:
                damage = 0
            
            lefthp = hp - damage
            lefthp = max(0, min(lefthp, targetsrpgcomp.maxhp))

            #结果修改
            findtarget.replace(SimpleRPGRoleComponent, targetsrpgcomp.name, targetsrpgcomp.maxhp, lefthp, targetsrpgcomp.attack, targetsrpgcomp.defense)

            ##死亡是关键
            isdead = (lefthp <= 0)

            ## 死后处理大流程，step1——道具怎么办？后续可以封装的复杂一些: 夺取唯一性道具
            if isdead:  
                self.unique_prop_be_taken_away(entity, findtarget)

            ## 可以加一些别的。。。。。。。。。。。。
            ## 比如杀人多了会被世界管理员记住——你是大坏蛋
            ## 。。。。。。。。。。。。。。。。。。。

            ## 死后处理大流程，step最后——死亡组件系统必须要添加
            if isdead:
                if not findtarget.has(DeadActionComponent):
                    #复制一个，不用以前的，怕GC不掉
                    findtarget.add(DeadActionComponent, ActorAction(action.name, action.actionname, action.values)) 

            ## 导演系统，单独处理，有旧的代码
            if isdead:
                notify_stage_director(context, entity, NPCKillSomeoneEvent(rpgcomp.name, value))
            else:
                notify_stage_director(context, entity, NPCAttackSomeoneEvent(rpgcomp.name, value, damage, lefthp, targetsrpgcomp.maxhp))
######################################################################################################################################################
    ## 杀死对方就直接夺取唯一性道具。
    def unique_prop_be_taken_away(self, thekiller: Entity, whoiskilled: Entity) -> None:

        file_system = self.context.file_system
        killer_rpg_comp: SimpleRPGRoleComponent = thekiller.get(SimpleRPGRoleComponent)
        be_killed_one_rpg_comp: SimpleRPGRoleComponent = whoiskilled.get(SimpleRPGRoleComponent)
        logger.info(f"{killer_rpg_comp.name} kill => {be_killed_one_rpg_comp.name}")
        
        hisprops = file_system.get_prop_files(be_killed_one_rpg_comp.name)
        for propfile in hisprops:
            if not propfile.prop.isunique():
                logger.info(f"the propfile {propfile.name} is not unique, so it will not be taken away.")
                continue
            # 交换文件，即交换道具文件即可
            file_system.exchange_prop_file(be_killed_one_rpg_comp.name, killer_rpg_comp.name, propfile.name)        
######################################################################################################################################################
    def final_attack_val(self, entity: Entity) -> int:
        # 最后的攻击力
        final: int = 0

        #基础的伤害
        rpgcomp: SimpleRPGRoleComponent = entity.get(SimpleRPGRoleComponent)
        final += cast(int, rpgcomp.attack)

        #计算武器带来的伤害
        if entity.has(SimpleRPGRoleWeaponComponent):
            weaponcomp: SimpleRPGRoleWeaponComponent = entity.get(SimpleRPGRoleWeaponComponent)
            final += cast(int, weaponcomp.attack)

        return final
######################################################################################################################################################
    def final_defense_val(self, entity: Entity) -> int:
        # 最后的防御力
        final: int = 0

        #基础防御力
        rpgcomp: SimpleRPGRoleComponent = entity.get(SimpleRPGRoleComponent)
        final += cast(int, rpgcomp.defense)

        #计算衣服带来的防御力
        if entity.has(SimpleRPGRoleArmorComponent):
            armorcomp: SimpleRPGRoleArmorComponent = entity.get(SimpleRPGRoleArmorComponent)
            final += cast(int, armorcomp.defense)

        return final
######################################################################################################################################################