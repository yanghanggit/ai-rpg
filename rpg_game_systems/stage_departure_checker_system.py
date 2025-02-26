from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from components.actions import (
    GoToAction,
    TagAction,
    DeadAction,
    WhisperAction,
)
from components.components import (
    ActorComponent,
    KickOffMessageComponent,
    StageComponent,
)
from game.rpg_game_context import RPGGameContext
import rpg_game_systems.prompt_utils
from typing import final, override, List, Set, NamedTuple, Dict
from rpg_game_systems.actor_entity_utils import ActorStatusEvaluator
from agent.agent_request_handler import AgentRequestHandler
from agent.agent_response_handler import AgentResponseHandler
from extended_systems.prop_file import (
    PropFile,
    generate_prop_file_for_stage_condition_prompt,
)
from game.rpg_game import RPGGame
from rpg_models.event_models import AgentEvent
from agent.lang_serve_agent import LangServeAgent
import rpg_game_systems.task_request_utils


################################################################################################################################################
def _generate_exit_conditions_prompt(
    actor_name: str,
    current_stage_name: str,
    actor_appearance: str,
    prop_files: List[PropFile],
) -> str:

    assert actor_appearance != ""

    prop_files_prompt: List[str] = []
    for prop_file in prop_files:
        prop_files_prompt.append(
            generate_prop_file_for_stage_condition_prompt(prop_file)
        )
    if len(prop_files_prompt) == 0:
        prop_files_prompt.append("无")

    return f"""# 提示: {actor_name} 试图离开场景：{current_stage_name}

## 判断步骤
1. 回顾状态：参考 {rpg_game_systems.prompt_utils.GeneralPromptTag.STAGE_EXIT_TAG} 确定场景当前状态。
2. 状态验证：结合事件回顾和场景设定，更新场景状态：
    - 事件回顾：分析角色行为、对话及道具使用的影响，以及场景的逻辑性变化。切勿推测未发生的活动。
    - 状态更新：推理并更新场景的最新状态。
3. 外观检查：确认 {actor_name} 的外观是否符合离开要求:
{actor_appearance}
4. 道具检查：确认 {actor_name} 的道具是否符合离开要求:
{"\n".join(prop_files_prompt)}

## 最终判断
完成以上步骤后，决定是否允许 {actor_name} 离开 {current_stage_name}。

## 输出要求
请遵循 输出格式指南。
{{ {WhisperAction.__name__}: ["@角色全名(对目标角色私下说明允许离开或不允许的原因，简单明确)"], {TagAction.__name__}: ["Yes/No" (是否允许离开)] }}

## 注意事项
在 {WhisperAction.__name__} 中仅说明不符合要求的单一原因，避免透露过多信息以免引起混乱或误导。"""


################################################################################################################################################
def _generate_exit_denial_prompt(
    actor_name: str, current_stage_name: str, denial_message: str
) -> str:
    return f"""# 提示: {actor_name} 试图离开场景: {current_stage_name}，但被拒绝。
## {current_stage_name} 给出的拒绝原因
{denial_message}"""


###############################################################################################################################################
@final
class InternalResponseHandler(AgentResponseHandler):

    def __init__(self, name: str, response_content: str) -> None:
        super().__init__(name, response_content)

    @property
    def is_allowed(self) -> bool:
        return self._parse_boolean(TagAction.__name__)

    @property
    def hint(self) -> str:
        ret = self._concatenate_values(WhisperAction.__name__)
        if ret == "":
            return "无"
        return ret


###############################################################################################################################################
@final
class StageDepartureCheckerSystem(ReactiveProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game
        self._react_entities_copy: List[Entity] = []

    ###############################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(GoToAction): GroupEvent.ADDED}

    ###############################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(GoToAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ###############################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        self._react_entities_copy = entities.copy()

    ###############################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        if len(self._react_entities_copy) == 0:
            return

        await self._execute2(self._react_entities_copy)
        self._react_entities_copy.clear()

    ###############################################################################################################################################
    async def _execute2(self, entities: List[Entity]) -> None:

        agent_tasks = self._initialize_agent_tasks(entities)
        if len(agent_tasks) == 0:
            return

        agent_responses = await rpg_game_systems.task_request_utils.gather(
            [task for task in agent_tasks.values()],
        )

        if len(agent_responses) == 0:
            # 直接放弃掉，全部删除
            self._remove_all_entities_actions(entities)
            return

        self._handle_agent_responses(agent_tasks)

    ######################################################################################################################################################
    def _initialize_agent_tasks(
        self, actor_entities: List[Entity]
    ) -> Dict[str, AgentRequestHandler]:

        ret: Dict[str, AgentRequestHandler] = {}

        for actor_entity in actor_entities:

            # 必须有场景
            current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
            assert current_stage_entity is not None
            if not self._has_conditions(current_stage_entity):
                # 没有离开条件就过
                continue

            # 加入返回值
            ret[self._context.safe_get_entity_name(actor_entity)] = (
                self._generate_agent_task(
                    actor_entity, self._context.safe_get_agent(current_stage_entity)
                )
            )

        return ret

    ######################################################################################################################################################
    def _generate_agent_task(
        self, actor_entity: Entity, current_stage_agent: LangServeAgent
    ) -> AgentRequestHandler:
        actor_status_evaluator = ActorStatusEvaluator(self._context, actor_entity)
        return AgentRequestHandler.create_with_input_only_context(
            current_stage_agent,
            _generate_exit_conditions_prompt(
                actor_name=actor_status_evaluator.actor_name,
                current_stage_name=actor_status_evaluator.stage_name,
                actor_appearance=actor_status_evaluator.appearance,
                prop_files=actor_status_evaluator.available_stage_condition_prop_files,
            ),
        )

    ######################################################################################################################################################
    def _handle_agent_responses(self, tasks: Dict[str, AgentRequestHandler]) -> None:

        for actor_name, stage_agent_task in tasks.items():

            actor_entity = self._context.get_actor_entity(actor_name)
            assert actor_entity is not None

            agent_response_handler = InternalResponseHandler(
                stage_agent_task.agent_name, stage_agent_task.response_content
            )

            if not agent_response_handler.is_allowed:

                # 通知失败
                self._context.notify_event(
                    set({actor_entity}),
                    AgentEvent(
                        message=_generate_exit_denial_prompt(
                            actor_name,
                            stage_agent_task.agent_name,
                            agent_response_handler.hint,
                        )
                    ),
                )

                # 删除所有行动, 因为不允许离开
                self._remove_action_components(actor_entity)

    ###############################################################################################################################################
    def _remove_all_entities_actions(
        self,
        actor_entities: List[Entity],
        action_components: Set[type[NamedTuple]] = {GoToAction},
    ) -> None:

        for actor_entity in actor_entities:
            self._remove_action_components(actor_entity, action_components)

    ###############################################################################################################################################
    def _remove_action_components(
        self,
        actor_entity: Entity,
        action_components: Set[type[NamedTuple]] = {GoToAction},
    ) -> None:

        for action_component in action_components:
            if actor_entity.has(action_component):
                actor_entity.remove(action_component)

    ###############################################################################################################################################
    def _has_conditions(self, stage_entity: Entity) -> bool:
        assert stage_entity.has(StageComponent)
        assert stage_entity.has(KickOffMessageComponent)
        return (
            rpg_game_systems.prompt_utils.GeneralPromptTag.STAGE_EXIT_TAG
            in stage_entity.get(KickOffMessageComponent).content
        )

    ###############################################################################################################################################
