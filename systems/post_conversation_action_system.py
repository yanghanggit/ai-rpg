from overrides import override
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import SpeakActionComponent, BroadcastActionComponent, WhisperActionComponent, PlayerComponent, ActorComponent
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.director_component import StageDirectorComponent
from typing import List, Set, Optional, Dict
from auxiliary.lang_serve_agent_system import LangServeAgentSystem, AgentRequestOption
from auxiliary.cn_builtin_prompt import batch_conversation_action_events_in_stage_prompt

# 这个类就是故意打包将对话类事件先进行一次request，如果LLM发现有政策问题就会抛异常，不会将污染的message加入chat history，这样就不可能进入chat_history。
# 这么做是防止玩家的对话内容包含了非法信息和违反政策的内容。
####################################################################################################
class PostConversationActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
        self.need_async_execute: bool = True
####################################################################################################
    @override 
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(any_of=[SpeakActionComponent, BroadcastActionComponent, WhisperActionComponent]): GroupEvent.ADDED}
####################################################################################################
    @override 
    def filter(self, entity: Entity) -> bool:
        # 如果去掉entity.has(PlayerComponent)。就是处理所有的Actor的对话事件，最保险的做法。
        # 有PlayerComponent就节省一些
        return entity.has(PlayerComponent) and entity.has(ActorComponent)
####################################################################################################
    @override 
    def react(self, entities: list[Entity]) -> None:

        ## 所有场景，发生了任何对话的事件
        stage_entities: Set[Entity] = set()
        for entity in entities:
            stage_entity = self.collect_stage(entity)
            if stage_entity is not None:
                stage_entities.add(stage_entity)

        for stage_entity in stage_entities:
            self.before_handle(stage_entity)
            self.handle(stage_entity, self.need_async_execute)
            self.after_handle(stage_entity)
####################################################################################################   
    def before_handle(self, stage_entity: Entity) -> None:
        assert stage_entity.has(StageDirectorComponent)
        safename = self.context.safe_get_entity_name(stage_entity)
        logger.warning(f"? {safename}:这里可以写，如果你说出来的话包涵了你目前不该知道的信息，就可以关掉。例如用broadcast喊某个地点，然后就能去了之类的")
####################################################################################################
    def after_handle(self, stage_entity: Entity) -> None:
        assert stage_entity.has(StageDirectorComponent)
        stage_director_comp: StageDirectorComponent = stage_entity.get(StageDirectorComponent)
        stage_director_comp.clear()
####################################################################################################
    def collect_stage(self, entity: Entity) -> Optional[Entity]:
        stage_entity = self.context.safe_get_stage_entity(entity)
        return stage_entity
####################################################################################################
    def handle(self, stage_entity: Entity, async_execute: bool) -> None:
        stage_director_comp: StageDirectorComponent = stage_entity.get(StageDirectorComponent)
        if len(stage_director_comp._events) == 0:
            return
        ##
        agent_connect_system: LangServeAgentSystem = self.context.agent_connect_system
        #处理场景的
        raw_events2stage = stage_director_comp.to_stage(stage_director_comp.name, self.context) 
        if len(raw_events2stage) > 0:
            batch_events2stage_prompt = self.batch_stage_events(stage_director_comp.name, raw_events2stage) 
            logger.info(f"PostConversationActionSystem: {stage_director_comp.name} : {batch_events2stage_prompt}")
            if async_execute:
                agent_connect_system.add_async_request_task(stage_director_comp.name, batch_events2stage_prompt, AgentRequestOption.ADD_PROMPT_TO_CHAT_HISTORY)
            else:
                self.imme_request(stage_director_comp.name, batch_events2stage_prompt)

        ### 处理Actor的
        actors_in_this_stage = self.context.actors_in_stage(stage_director_comp.name)
        for _entity in actors_in_this_stage:
            actor_comp: ActorComponent = _entity.get(ActorComponent)
            raw_events2actor = stage_director_comp.to_actor(actor_comp.name, self.context)     
            if len(raw_events2actor) > 0:
                batch_events2actor_prompt = self.batch_actor_events(stage_director_comp.name, raw_events2actor)
                logger.info(f"PostConversationActionSystem: {actor_comp.name} : {batch_events2actor_prompt}")
                if async_execute:
                    agent_connect_system.add_async_request_task(actor_comp.name, batch_events2actor_prompt, AgentRequestOption.ADD_PROMPT_TO_CHAT_HISTORY)
                else:
                    self.imme_request(actor_comp.name, batch_events2actor_prompt)
####################################################################################################
    def imme_request(self, name: str, prompt: str) -> None:
        agent_connect_system: LangServeAgentSystem = self.context.agent_connect_system
        try:
            response = agent_connect_system.agent_request(name, prompt)
            if response is None:
                logger.error(f"imme_request: {name} request error.")
        except Exception as e:
                logger.error(f"imme_request: {name} request error.")
####################################################################################################
    def batch_stage_events(self, stagename: str, events2stage: List[str]) -> str:
        return batch_conversation_action_events_in_stage_prompt(stagename, events2stage, self.context)
####################################################################################################
    def batch_actor_events(self, stagename: str, events2actor: List[str]) -> str:
        return batch_conversation_action_events_in_stage_prompt(stagename, events2actor, self.context)
####################################################################################################
    async def async_post_execute(self) -> None:
        # 并行执行requests
        agent_connect_system = self.context.agent_connect_system
        if len(agent_connect_system._async_request_tasks) == 0:
            return
        logger.debug(f"PostConversationActionSystem async_post_execute begin.")     
        request_result = await agent_connect_system.run_async_requet_tasks("PostConversationActionSystem")
        responses: Dict[str, Optional[str]] = request_result[0]
        #正常流程
        for name, response in responses.items():
            if response is None:
                logger.error(f"PostConversationActionSystem: {name} response is None or empty.")
            else:
                # AI的回复不要，防止污染上下文
                logger.debug(f"PostConversationActionSystem: {name} response is {response}")

        logger.debug(f"PostConversationActionSystem async_post_execute end.")
####################################################################################################
