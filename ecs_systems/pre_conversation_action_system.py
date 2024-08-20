from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from overrides import override
from ecs_systems.action_components import SpeakAction, BroadcastAction, WhisperAction
from ecs_systems.components import PlayerComponent, ActorComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_agent.lang_serve_agent_request_task import (
    LangServeAgentRequestTask,
    LangServeAgentAsyncRequestTasksGather,
)
from my_agent.agent_action import AgentAction
from typing import Dict, cast, List
import copy


class PreConversationActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
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

        prompt = f"""# 玩家输入了如下对话类型事件，请你检查

## {BroadcastAction.__name__}:广播事件,公开说话内容
{broadcast_content}
## {SpeakAction.__name__}:说话事件,对某角色说,场景其他角色可以听见
{"\n".join(speak_content_list)}
## {WhisperAction.__name__}:私语事件,只有目标角色可以听见
{"\n".join(whisper_content_list)}

## 检查规则
- 对话内容是否违反政策。
- 对话内容是否有不当的内容。
- 对话对容是否有超出游戏范围的内容。例如，玩家说了一些关于游戏外的事情或者说出不符合游戏世界观与历史背景的事件。
"""

        task = LangServeAgentRequestTask.create_for_checking_prompt(agent, prompt)
        if task is None:
            return

        tasks[safe_name] = task

    def get_broadcast_content(self, player_entity: Entity) -> str:
        if not player_entity.has(BroadcastAction):
            return "无"
        broadcast_action = cast(AgentAction, player_entity.get(BroadcastAction).action)
        return broadcast_action.join_values()

    def get_speak_content(self, player_entity: Entity) -> List[str]:
        if not player_entity.has(SpeakAction):
            return ["无"]
        speak_action = cast(AgentAction, player_entity.get(SpeakAction).action)
        return copy.copy(speak_action._values)

    def get_whisper_content(self, player_entity: Entity) -> List[str]:
        if not player_entity.has(WhisperAction):
            return ["无"]
        whisper_action = cast(AgentAction, player_entity.get(WhisperAction).action)
        return copy.copy(whisper_action._values)

    async def async_post_execute(self) -> None:
        if len(self._tasks) == 0:
            return
        gather = LangServeAgentAsyncRequestTasksGather(
            "PreConversationActionSystem", self._tasks
        )
        await gather.gather()
        self._tasks.clear()
