from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from overrides import override
from gameplay_systems.action_components import (
    SpeakAction,
    BroadcastAction,
    WhisperAction,
)
from gameplay_systems.components import PlayerComponent, ActorComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_agent.lang_serve_agent_request_task import (
    LangServeAgentRequestTask,
    LangServeAgentAsyncRequestTasksGather,
)
from typing import Dict, List
import copy
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from rpg_game.rpg_game import RPGGame


class PreConversationActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._tasks: Dict[str, LangServeAgentRequestTask] = {}

    #################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {
            Matcher(
                any_of=[SpeakAction, BroadcastAction, WhisperAction]
            ): GroupEvent.ADDED
        }

    #################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayerComponent) and entity.has(ActorComponent)

    #################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        self._tasks.clear()
        for player_entity in entities:
            self.fill_task(player_entity, self._tasks)

    #################################################################################################################################################
    def fill_task(
        self, player_entity: Entity, tasks: Dict[str, LangServeAgentRequestTask]
    ) -> None:
        safe_name = self._context.safe_get_entity_name(player_entity)
        agent = self._context._langserve_agent_system.get_agent(safe_name)
        if agent is None:
            return

        broadcast_content = self.get_broadcast_content(player_entity)
        speak_content_list = self.get_speak_content(player_entity)
        whisper_content_list = self.get_whisper_content(player_entity)

        prompt = builtin_prompt.make_player_conversation_check_prompt(
            broadcast_content, speak_content_list, whisper_content_list
        )

        task = LangServeAgentRequestTask.create_without_context(agent, prompt)
        if task is None:
            return

        tasks[safe_name] = task

    #################################################################################################################################################
    def get_broadcast_content(self, player_entity: Entity) -> str:
        if not player_entity.has(BroadcastAction):
            return ""
        broadcast_action = player_entity.get(BroadcastAction)
        return " ".join(broadcast_action.values)

    #################################################################################################################################################
    def get_speak_content(self, player_entity: Entity) -> List[str]:
        if not player_entity.has(SpeakAction):
            return []
        speak_action = player_entity.get(SpeakAction)
        return copy.copy(speak_action.values)

    #################################################################################################################################################
    def get_whisper_content(self, player_entity: Entity) -> List[str]:
        if not player_entity.has(WhisperAction):
            return []
        whisper_action = player_entity.get(WhisperAction)
        return copy.copy(whisper_action.values)

    #################################################################################################################################################
    async def post_execute(self) -> None:
        if len(self._tasks) == 0:
            return

        gather = LangServeAgentAsyncRequestTasksGather("", self._tasks)

        response = await gather.gather()
        if len(response) == 0:
            self.remove_all()
            return

        self.on_response(self._tasks)
        self._tasks.clear()

    #################################################################################################################################################
    def remove_all(self) -> None:

        actor_entities = self._context.get_group(
            Matcher(
                all_of=[ActorComponent, PlayerComponent],
                any_of=[SpeakAction, BroadcastAction, WhisperAction],
            )
        ).entities.copy()

        for actor_entity in actor_entities:
            self.remove_action(actor_entity)

    #################################################################################################################################################
    def remove_action(self, player_entity: Entity) -> None:
        if player_entity.has(SpeakAction):
            player_entity.remove(SpeakAction)

        if player_entity.has(BroadcastAction):
            player_entity.remove(BroadcastAction)

        if player_entity.has(WhisperAction):
            player_entity.remove(WhisperAction)

    #################################################################################################################################################
    def on_response(self, tasks: Dict[str, LangServeAgentRequestTask]) -> None:
        for name, task in tasks.items():

            if task is None:
                continue

            player_entity = self._context.get_actor_entity(name)
            if player_entity is None:
                continue

            if task.response is None:
                # 说明可能在langserve中出现了问题，就是没有任何返回值。
                self.remove_action(player_entity)

    #################################################################################################################################################
