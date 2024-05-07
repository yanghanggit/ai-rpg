from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import (
    LeaveForActionComponent, 
    NPCComponent,
    PlayerComponent
    )
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.director_component import notify_stage_director, StageDirectorComponent
from auxiliary.director_event import (
    NPCLeaveForStageEvent, 
    NPCEnterStageEvent)
from typing import cast
from auxiliary.player_proxy import notify_player_proxy
from auxiliary.cn_builtin_prompt import force_direct_npc_events_before_leave_stage_prompt


###############################################################################################################################################
class LeaveActionHelper:

    def __init__(self, context: ExtendedContext, who_wana_leave: Entity, target_stage_name: str) -> None:
        self.context = context
        self.who_wana_leave_entity = who_wana_leave
        self.current_stage_name = cast(NPCComponent, who_wana_leave.get(NPCComponent)).current_stage
        self.current_stage_entity = self.context.getstage(self.current_stage_name)
        self.target_stage_name = target_stage_name
        self.target_stage_entity = self.context.getstage(target_stage_name)

###############################################################################################################################################
class LeaveForActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(LeaveForActionComponent): GroupEvent.ADDED}

    def filter(self, entity: Entity) -> bool:
        return entity.has(LeaveForActionComponent) and entity.has(NPCComponent)

    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  LeaveForActionSystem  >>>>>>>>>>>>>>>>>")
        self.leavefor(entities)

    ###############################################################################################################################################
    def leavefor(self, entities: list[Entity]) -> None:

        for entity in entities:
            if not entity.has(NPCComponent):
                logger.warning(f"LeaveForActionSystem: {entity} is not NPC?!")
                continue
            
            leavecomp: LeaveForActionComponent = entity.get(LeaveForActionComponent)
            action: ActorAction = leavecomp.action
            if len(action.values) == 0:
               continue
   
            stagename = action.values[0]
            handle = LeaveActionHelper(self.context, entity, stagename)
            if handle.target_stage_entity is None or handle.current_stage_entity is None or handle.target_stage_entity == handle.current_stage_entity:
                continue

            if handle.current_stage_entity is not None:
                #离开前的处理
                self.before_leave_stage(handle)
                #离开
                self.leave_stage(handle)

            #进入新的场景
            self.enter_stage(handle)
    ###############################################################################################################################################            
    def enter_stage(self, helper: LeaveActionHelper) -> None:
        entity = helper.who_wana_leave_entity
        current_stage_name = helper.current_stage_name
        target_stage_name = helper.target_stage_name
        target_stage_entity = helper.target_stage_entity
        assert target_stage_entity is not None
        npccomp: NPCComponent = entity.get(NPCComponent)

        replace_name = npccomp.name
        replace_current_stage = target_stage_name
        entity.replace(NPCComponent, replace_name, replace_current_stage)
        self.context.change_stage_tag_component(entity, current_stage_name, replace_current_stage)

        notify_stage_director(self.context, entity, NPCEnterStageEvent(npccomp.name, target_stage_name, current_stage_name))
        #self.notify_director_enter_stage(target_stage_entity, npccomp.name, target_stage_name)
       
        # 处理在离开时被攻击的对象xw
        #self.npc_leaving_but_attacked(entity, target_stage_entity)
    ###############################################################################################################################################
    def before_leave_stage(self, helper: LeaveActionHelper) -> None:
        #目前就是强行刷一下history
        self.force_direct(helper)
###############################################################################################################################################
    def force_direct(self, helper: LeaveActionHelper) -> None:
         #
        current_stage_entity = helper.current_stage_entity
        assert current_stage_entity is not None

        #
        directorcomp: StageDirectorComponent = current_stage_entity.get(StageDirectorComponent)
        safe_npc_name = self.context.safe_get_entity_name(helper.who_wana_leave_entity)
        #
        events2npc = directorcomp.tonpc(safe_npc_name, self.context)            
        newmsg = "\n".join(events2npc)
        if len(newmsg) > 0:
            #添加history
            prompt = force_direct_npc_events_before_leave_stage_prompt(newmsg, helper.current_stage_name, self.context)
            self.context.safe_add_human_message_to_entity(helper.who_wana_leave_entity, prompt)
                
            #如果是player npc就再补充这个方法，通知调用客户端
            if helper.who_wana_leave_entity.has(PlayerComponent):
                notify_player_proxy(helper.who_wana_leave_entity, newmsg, events2npc)
    ###############################################################################################################################################
    def leave_stage(self, helper: LeaveActionHelper) -> None:
        entity: Entity = helper.who_wana_leave_entity
        npccomp: NPCComponent = entity.get(NPCComponent)
        assert helper.current_stage_entity is not None
        currentstage: Entity = helper.current_stage_entity

        replace_name = npccomp.name
        replace_current_stage = "" #设置空！！！！！
        entity.replace(NPCComponent, replace_name, replace_current_stage)
        
        self.context.change_stage_tag_component(entity, helper.current_stage_name, replace_current_stage)

        notify_stage_director(self.context, entity, NPCLeaveForStageEvent(npccomp.name, helper.current_stage_name, helper.target_stage_name))
        #self.notify_director_leave_for_stage(currentstage, npccomp.name, handle.current_stage_name, handle.target_stage_name)
    ###############################################################################################################################################
    # def notify_director_leave_for_stage(self, stageentity: Entity, npcname: str, cur_stage_name: str, target_stage_name: str) -> None:
    #     if stageentity is None or not stageentity.has(StageDirectorComponent):
    #         return
    #     directorcomp: StageDirectorComponent = stageentity.get(StageDirectorComponent)
    #     leaveforstageevent = NPCLeaveForStageEvent(npcname, cur_stage_name, target_stage_name)
    #     directorcomp.addevent(leaveforstageevent)
    # ###############################################################################################################################################
    # def notify_director_enter_stage(self, stageentity: Entity, npcname: str, target_stage_name: str) -> None:
    #     if stageentity is None or not stageentity.has(StageDirectorComponent):
    #         return
    #     directorcomp: StageDirectorComponent = stageentity.get(StageDirectorComponent)
    #     enterstageevent = NPCEnterStageEvent(npcname, target_stage_name)
    #     directorcomp.addevent(enterstageevent)
    ###############################################################################################################################################
    # def npc_leaving_but_attacked(self, attacked_entity: Entity, target_stage_entity: Entity) -> None:
    #     attacker_entities: set[Entity] = self.context.get_group(Matcher(all_of=[FightActionComponent])).entities
    #     for attacker_entity in attacker_entities:
    #         attacker_fight_action_comp: FightActionComponent = attacker_entity.get(FightActionComponent)
    #         attacker_fight_action: ActorAction = attacker_fight_action_comp.action
    #         for attacked in attacker_fight_action.values:
    #             attacker_rpg_comp: SimpleRPGRoleComponent = attacker_entity.get(SimpleRPGRoleComponent)
    #             attacked_rpg_comp: SimpleRPGRoleComponent = attacked_entity.get(SimpleRPGRoleComponent)
    #             if attacked == attacked_rpg_comp.name:
    #                 attacked_event = NPCAttackSomeoneEvent(attacker_rpg_comp.name, attacked_rpg_comp.name, attacked_rpg_comp.attack, attacked_rpg_comp.hp + attacked_rpg_comp.attack, attacked_rpg_comp.maxhp)
    #                 target_stage_director: StageDirectorComponent = target_stage_entity.get(StageDirectorComponent)
    #                 target_stage_director.addevent(attacked_event)
         
