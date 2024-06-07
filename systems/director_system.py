from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.components import StageComponent, ActorComponent, PlayerComponent
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.director_component import StageDirectorComponent
from auxiliary.player_proxy import add_client_actor_message
from auxiliary.cn_builtin_prompt import stage_director_begin_prompt, stage_director_end_prompt, stage_director_event_wrap_prompt

class DirectorSystem(ExecuteProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
###################################################################################################################
    def execute(self) -> None:
        self.handle()
        self.director_clear()
###################################################################################################################
    def handle(self) -> None:
        entities = self.context.get_group(Matcher(all_of=[StageComponent, StageDirectorComponent])).entities
        for entity in entities:
            logger.debug('=' *50)
            self.handle_stage(entity)
            logger.debug('=' *50)
            self.handle_npcs_in_this_stage(entity)
            logger.debug('=' *50)
###################################################################################################################   
    def director_clear(self) -> None:
        entities = self.context.get_group(Matcher(all_of=[StageComponent, StageDirectorComponent])).entities
        for entity in entities:
            directorcomp: StageDirectorComponent = entity.get(StageDirectorComponent)
            directorcomp.clear()
###################################################################################################################
    def handle_stage(self, entitystage: Entity) -> None:
        assert entitystage.has(StageComponent)
        stagecomp: StageComponent = entitystage.get(StageComponent)
        directorcomp: StageDirectorComponent = entitystage.get(StageDirectorComponent)
        events2stage = directorcomp.to_stage(stagecomp.name, self.context)  
        for event in events2stage:
            logger.debug(f"director:{stagecomp.name}:{event}")
            self.context.safe_add_human_message_to_entity(entitystage, event)       
###################################################################################################################
    def handle_npcs_in_this_stage(self, entitystage: Entity) -> None:
        assert entitystage.has(StageComponent)
        stagecomp: StageComponent = entitystage.get(StageComponent)
        npcs_int_this_stage = self.context.npcs_in_this_stage(stagecomp.name)
        for npcentity in npcs_int_this_stage:
            director_events_to_npc(self.context, npcentity)
###################################################################################################################
def director_events_to_npc(context: ExtendedContext, npc_entity: Entity) -> None:
    stage_entity = context.safe_get_stage_entity(npc_entity)
    if stage_entity is None:
        return
    stage_director_comp: StageDirectorComponent = stage_entity.get(StageDirectorComponent)
    assert stage_director_comp is not None

     ### 添加消息！
    npccomp: ActorComponent = npc_entity.get(ActorComponent)

    events2npc = stage_director_comp.to_actor(npccomp.name, context)    
    if len(events2npc) == 0:
        return

    ### 标记开始
    context.safe_add_human_message_to_entity(npc_entity, stage_director_begin_prompt(stage_director_comp.name, len(events2npc)))

    for index, event in enumerate(events2npc):
        wrap_prompt = stage_director_event_wrap_prompt(event, index)
        logger.debug(f"director:{npccomp.name}:{event}")
        context.safe_add_human_message_to_entity(npc_entity, wrap_prompt)

    ## 标记结束
    context.safe_add_human_message_to_entity(npc_entity, stage_director_end_prompt(stage_director_comp.name, len(events2npc)))

    # 通知客户端显示
    if npc_entity.has(PlayerComponent):
        events2player = stage_director_comp.to_player(npccomp.name, context)
        for event in events2player:
            add_client_actor_message(npc_entity, event)
###################################################################################################################
    