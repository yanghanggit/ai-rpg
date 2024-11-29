from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from overrides import override
from components.action_components import (
    SpeakAction,
    AnnounceAction,
    WhisperAction,
    MindVoiceAction,
    TagAction,
)
from components.components import (
    PlayerComponent,
    ActorComponent,
    AgentPingFlagComponent,
)
from game.rpg_entitas_context import RPGEntitasContext
from agent.agent_task import AgentTask
from typing import List, final
import copy
from game.rpg_game import RPGGame
from agent.agent_plan import AgentPlanResponse


################################################################################################################################################
def _generate_conversation_check_prompt(
    announce_content: str,
    speak_content_list: List[str],
    whisper_content_list: List[str],
) -> str:

    # 生成对话检查的提示
    announce_prompt = announce_content != "" and announce_content or "无"
    speak_content_list_prompt = (
        len(speak_content_list) > 0 and "\n".join(speak_content_list) or "无"
    )
    whisper_content_list_prompt = (
        len(whisper_content_list) > 0 and "\n".join(whisper_content_list) or "无"
    )

    return f"""# 提示: 玩家输入了如下对话类型事件，请你检查是否符合游戏规则。
    
## {AnnounceAction.__name__}
{announce_prompt}

## {SpeakAction.__name__}
{speak_content_list_prompt}

## {WhisperAction.__name__}
{whisper_content_list_prompt}

## 检查要求与原则
- 对话内容是否违反政策。
- 对话内容是否有不当的内容。
- 对话对容是否有超出游戏范围的内容。例如，玩家说了一些关于游戏外的事情，或者说出不符合游戏世界观与历史背景的事件。

## 输出要求
- 请遵循输出格式指南。
- 返回结果仅包含：{MindVoiceAction.__name__} 和 {TagAction.__name__}。

## 格式示例：
{{ "{MindVoiceAction.__name__}":["输出你的最终判断结果，说明是否符合，并附上原因"], "{TagAction.__name__}":["Yes/No"（符合/不符合）] }}"""


################################################################################################################################################
################################################################################################################################################
################################################################################################################################################
@final
class InternalPlanResponse(AgentPlanResponse):

    def __init__(self, name: str, input_str: str) -> None:
        super().__init__(name, input_str)

    @property
    def is_allowed(self) -> bool:
        return self._parse_boolean(TagAction.__name__)


################################################################################################################################################
################################################################################################################################################
################################################################################################################################################


@final
class PreConversationActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._entities_copy: List[Entity] = []

    #################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {
            Matcher(
                any_of=[SpeakAction, AnnounceAction, WhisperAction]
            ): GroupEvent.ADDED
        }

    #################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PlayerComponent)
            and entity.has(ActorComponent)
            and entity.has(AgentPingFlagComponent)
        )

    #################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        self._entities_copy = entities.copy()

    #################################################################################################################################################
    async def a_execute2(self) -> None:
        await self._execute_agent_tasks(self._entities_copy)
        self._entities_copy.clear()

    #################################################################################################################################################
    async def _execute_agent_tasks(self, entities: List[Entity]) -> None:

        if len(entities) == 0:
            return

        # 生成agent任务
        agent_tasks: List[AgentTask] = []
        for player_entity in entities:
            agent_tasks.append(self._populate_agent_task(player_entity))

        # 执行agent任务
        await AgentTask.gather(agent_tasks)

        # 处理agent任务的返回值
        self._process_response_tasks(agent_tasks)

    #################################################################################################################################################
    def _populate_agent_task(
        self,
        player_entity: Entity,
    ) -> AgentTask:
        return AgentTask.create_without_context(
            self._context.safe_get_agent(player_entity),
            _generate_conversation_check_prompt(
                self._get_announce_content(player_entity),
                self._get_speak_content(player_entity),
                self._get_whisper_content(player_entity),
            ),
        )

    #################################################################################################################################################
    def _get_announce_content(self, player_entity: Entity) -> str:
        if not player_entity.has(AnnounceAction):
            return ""
        announce_action = player_entity.get(AnnounceAction)
        return " ".join(announce_action.values)

    #################################################################################################################################################
    def _get_speak_content(self, player_entity: Entity) -> List[str]:
        if not player_entity.has(SpeakAction):
            return []
        speak_action = player_entity.get(SpeakAction)
        return copy.copy(speak_action.values)

    #################################################################################################################################################
    def _get_whisper_content(self, player_entity: Entity) -> List[str]:
        if not player_entity.has(WhisperAction):
            return []
        whisper_action = player_entity.get(WhisperAction)
        return copy.copy(whisper_action.values)

    #################################################################################################################################################
    def _clear_player_communication_actions(self, player_entity: Entity) -> None:

        if player_entity.has(SpeakAction):
            player_entity.remove(SpeakAction)

        if player_entity.has(AnnounceAction):
            player_entity.remove(AnnounceAction)

        if player_entity.has(WhisperAction):
            player_entity.remove(WhisperAction)

    #################################################################################################################################################
    def _process_response_tasks(self, tasks: List[AgentTask]) -> None:
        for task in tasks:
            player_entity = self._context.get_actor_entity(task.agent_name)
            assert player_entity is not None
            if player_entity is None:
                continue

            # 处理agent任务的返回值
            plan_response = InternalPlanResponse(task.agent_name, task.response_content)
            if not plan_response.is_allowed:
                self._clear_player_communication_actions(player_entity)

    #################################################################################################################################################
