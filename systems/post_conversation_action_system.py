from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import SpeakActionComponent, BroadcastActionComponent, WhisperActionComponent, PlayerComponent, NPCComponent
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.director_component import StageDirectorComponent
from typing import List
from auxiliary.agent_connect_system import AgentConnectSystem

# todo 如果测试没问题，最好改成并发的
# 这个类就是故意打包将对话类事件先进行一次request，如果LLM发现有政策问题就会抛异常，不会将污染的message加入chat history，这样就不可能进入chat_history。
# 这么做是防止玩家的对话内容包含了非法信息和违反政策的内容。
####################################################################################################
class PostConversationActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(any_of=[SpeakActionComponent, BroadcastActionComponent, WhisperActionComponent]): GroupEvent.ADDED}
####################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayerComponent) and entity.has(NPCComponent)
####################################################################################################
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.before_handle(entity)
            self.handle(entity)
            self.after_handle(entity)
####################################################################################################   
    def before_handle(self, entity: Entity) -> None:
        logger.warning(f"这里可以写，如果你说出来的话包涵了你目前不该知道的信息，就可以关掉。例如用broadcast喊某个地点，然后就能去了之类的")
####################################################################################################
    def after_handle(self, entity: Entity) -> None:
        stage_entity = self.context.safe_get_stage_entity(entity)
        if stage_entity is None:
            return
        stage_director_comp: StageDirectorComponent = stage_entity.get(StageDirectorComponent)
        stage_director_comp.events.clear()
####################################################################################################
    def handle(self, entity: Entity) -> None:
        stage_entity = self.context.safe_get_stage_entity(entity)
        if stage_entity is None:
            return
        stage_director_comp: StageDirectorComponent = stage_entity.get(StageDirectorComponent)
        if len(stage_director_comp.events) == 0:
            return
        ##
        agent_connect_system: AgentConnectSystem = self.context.agent_connect_system
        #
        events2stage = stage_director_comp.tostage(stage_director_comp.name, self.context) 
        batch_events2stage = self.batch_stage_events(events2stage) 
        try:
            response = agent_connect_system.request(stage_director_comp.name, batch_events2stage)
            if response is None:
                logger.error(f"handle: {stage_director_comp.name} request error.")
        except Exception as e:
            logger.error(f"handle: {stage_director_comp.name} request error.")

        ### 处理NPC的
        npcs_in_this_stage = self.context.npcs_in_this_stage(stage_director_comp.name)
        for npc_entity in npcs_in_this_stage:
            if npc_entity == entity:
                continue
            ###
            npccomp: NPCComponent = npc_entity.get(NPCComponent)
            events2npc = stage_director_comp.tonpc(npccomp.name, self.context)     
            batch_events2npc = self.batch_npc_events(events2npc)
            try:
                response = agent_connect_system.request(npccomp.name, batch_events2npc)
                if response is None:
                    logger.error(f"handle: {npccomp.name} request error.")
            except Exception as e:
                logger.error(f"handle: {npccomp.name} request error.")
####################################################################################################
    def batch_stage_events(self, events2stage: List[str]) -> str:
        joinstr: str = "\n".join(events2stage)
        prompt = f""" # 当前场景发生了如下对话类型事件，请注意:\n{joinstr}"""
        return prompt
####################################################################################################
    def batch_npc_events(self, events2npc: List[str]) -> str:
        joinstr: str = "\n".join(events2npc)
        prompt = f""" # 当前场景发生了如下对话类型事件，请注意:\n{joinstr}"""
        return prompt
####################################################################################################
