from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from overrides import override
from my_components.action_components import (
    SpeakAction,
    BroadcastAction,
    WhisperAction,
)
from my_components.components import (
    PlayerComponent,
    ActorComponent,
    AgentConnectionFlagComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_agent.agent_task import AgentTask
from typing import Dict, List, final
import copy
from rpg_game.rpg_game import RPGGame


################################################################################################################################################
def _generate_conversation_check_prompt(
    input_broadcast_content: str,
    input_speak_content_list: List[str],
    input_whisper_content_list: List[str],
) -> str:

    broadcast_prompt = input_broadcast_content != "" and input_broadcast_content or "无"
    speak_content_prompt = (
        len(input_speak_content_list) > 0
        and "\n".join(input_speak_content_list)
        or "无"
    )
    whisper_content_prompt = (
        len(input_whisper_content_list) > 0
        and "\n".join(input_whisper_content_list)
        or "无"
    )

    prompt = f"""# 玩家输入了如下对话类型事件，请你检查

## {BroadcastAction.__name__}
{broadcast_prompt}
## {SpeakAction.__name__}
{speak_content_prompt}
## {WhisperAction.__name__}
{whisper_content_prompt}
## 检查规则
- 对话内容是否违反政策。
- 对话内容是否有不当的内容。
- 对话对容是否有超出游戏范围的内容。例如，玩家说了一些关于游戏外的事情，或者说出不符合游戏世界观与历史背景的事件。
"""
    return prompt


@final
class PreConversationActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._tasks: Dict[str, AgentTask] = {}

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
        return (
            entity.has(PlayerComponent)
            and entity.has(ActorComponent)
            and entity.has(AgentConnectionFlagComponent)
        )

    #################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        self._tasks.clear()
        for player_entity in entities:
            self.fill_task(player_entity, self._tasks)

    #################################################################################################################################################
    def fill_task(self, player_entity: Entity, tasks: Dict[str, AgentTask]) -> None:
        safe_name = self._context.safe_get_entity_name(player_entity)
        agent = self._context.agent_system.get_agent(safe_name)
        if agent is None:
            return

        broadcast_content = self.get_broadcast_content(player_entity)
        speak_content_list = self.get_speak_content(player_entity)
        whisper_content_list = self.get_whisper_content(player_entity)

        prompt = _generate_conversation_check_prompt(
            broadcast_content, speak_content_list, whisper_content_list
        )

        tasks[safe_name] = AgentTask.create_standalone(agent, prompt)

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
    async def a_execute2(self) -> None:
        if len(self._tasks) == 0:
            return

        responses = await AgentTask.gather([task for task in self._tasks.values()])
        if len(responses) == 0:
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
    def on_response(self, tasks: Dict[str, AgentTask]) -> None:
        for name, task in tasks.items():

            player_entity = self._context.get_actor_entity(name)
            if player_entity is None:
                continue

            if task.response is None:
                # 说明可能在langserve中出现了问题，就是没有任何返回值。
                self.remove_action(player_entity)

    #################################################################################################################################################
