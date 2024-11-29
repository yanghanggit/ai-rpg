from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from components.action_components import (
    GoToAction,
    TagAction,
    DeadAction,
    WhisperAction,
)
from components.components import (
    ActorComponent,
    StageComponent,
    KickOffContentComponent,
)
from game.rpg_entitas_context import RPGEntitasContext
import gameplay_systems.prompt_utils as prompt_utils
from typing import final, override, List, Set, Any, Dict
from gameplay_systems.actor_entity_utils import ActorStatusEvaluator
from agent.agent_task import AgentTask
from agent.agent_plan import AgentPlanResponse
from extended_systems.prop_file import (
    PropFile,
    generate_prop_file_for_stage_condition_prompt,
)
from game.rpg_game import RPGGame
from models.event_models import AgentEvent
from loguru import logger
from agent.lang_serve_agent import LangServeAgent


################################################################################################################################################
def _generate_stage_entry_conditions_prompt(
    actor_name: str,
    target_stage_name: str,
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

    return f"""# 提示: {actor_name} 试图进入场景：{target_stage_name}

## 判断步骤
1. 回顾状态：参考 {prompt_utils.PromptTag.STAGE_ENTRY_TAG} 确定场景当前状态。
2. 状态验证：结合事件回顾和场景设定，更新场景状态：
    - 事件回顾：分析角色行为、对话及道具使用的影响，以及场景的逻辑性变化。切勿推测未发生的活动。
    - 状态更新：推理并更新场景的最新状态。
3. 外观检查：确认 {actor_name} 的外观是否符合进入要求:
{actor_appearance}
4. 道具检查：确认 {actor_name} 的道具是否符合进入要求:
{"\n".join(prop_files_prompt)}

## 最终判断
完成以上步骤后，决定是否允许 {actor_name} 进入 {target_stage_name}。

## 输出要求
请遵循 输出格式指南。
{{ {WhisperAction.__name__}: ["@角色全名(对目标角色私下说明允许进入或不允许的原因，简单明确)"], {TagAction.__name__}: ["Yes/No" (是否允许进入)] }}

## 注意事项
在 {WhisperAction.__name__} 中仅说明不符合要求的单一原因，避免透露过多信息以免引起混乱或误导。"""


################################################################################################################################################
def _generate_entry_denial_prompt(
    actor_name: str, target_stage_name: str, denial_message: str
) -> str:
    return f"""# 提示: {actor_name} 试图进入场景：{target_stage_name}，但被拒绝。
## {target_stage_name} 给出的拒绝原因
{denial_message}"""


################################################################################################################################################
@final
class InternalPlanResponse(AgentPlanResponse):

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
class StageEntranceCheckerSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
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

        agent_responses = await AgentTask.gather(
            [task for task in agent_tasks.values()],
        )

        if len(agent_responses) == 0:
            self._remove_all_entities_actions(entities)
            return

        self._handle_agent_responses(agent_tasks)

    ######################################################################################################################################################
    def _initialize_agent_tasks(
        self, actor_entities: List[Entity]
    ) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        for actor_entity in actor_entities:

            target_stage_entity = self._context.get_stage_entity(
                self._resolve_actor_target_stage(actor_entity)
            )

            if target_stage_entity is None:
                logger.error(
                    f"target_stage_entity is None!!!!!!!!"
                )  # todo 这里应该通知下，这不是一个合理的场景
                self._remove_action_components(actor_entity)
                continue

            if not self._has_conditions(target_stage_entity):
                continue

            # 必须是能推理的场景
            target_stage_agent = self._context.safe_get_agent(target_stage_entity)

            # 加入返回值
            ret[self._context.safe_get_entity_name(actor_entity)] = (
                self._generate_agent_task(
                    actor_entity, target_stage_entity, target_stage_agent
                )
            )

        return ret

    ######################################################################################################################################################
    def _generate_agent_task(
        self,
        actor_entity: Entity,
        target_stage_entity: Entity,
        target_stage_agent: LangServeAgent,
    ) -> AgentTask:

        # target_stage_name = self._context.safe_get_entity_name(target_stage_entity)
        actor_status_evaluator = ActorStatusEvaluator(self._context, actor_entity)
        prompt = _generate_stage_entry_conditions_prompt(
            actor_name=actor_status_evaluator.actor_name,
            target_stage_name=target_stage_agent.name,
            actor_appearance=actor_status_evaluator.appearance,
            prop_files=actor_status_evaluator.available_stage_condition_prop_files,
        )

        return AgentTask.create_with_input_only_context(target_stage_agent, prompt)

    ###############################################################################################################################################
    def _resolve_actor_target_stage(self, actor_entity: Entity) -> str:
        assert actor_entity.has(ActorComponent)
        assert actor_entity.has(GoToAction)
        goto_action = actor_entity.get(GoToAction)
        if len(goto_action.values) == 0:
            return ""
        return str(goto_action.values[0])

    ######################################################################################################################################################
    def _handle_agent_responses(self, tasks: Dict[str, AgentTask]) -> None:

        for actor_name, stage_agent_task in tasks.items():

            agent_response_plan = InternalPlanResponse(
                stage_agent_task.agent_name, stage_agent_task.response_content
            )
            if not agent_response_plan.is_allowed:

                actor_entity = self._context.get_actor_entity(actor_name)
                assert actor_entity is not None

                self._context.notify_event(
                    set({actor_entity}),
                    AgentEvent(
                        message=_generate_entry_denial_prompt(
                            actor_name,
                            stage_agent_task.agent_name,
                            agent_response_plan.hint,
                        )
                    ),
                )

                self._remove_action_components(actor_entity)

    ###############################################################################################################################################
    def _remove_all_entities_actions(
        self,
        actor_entities: List[Entity],
        action_components: Set[type[Any]] = {GoToAction},
    ) -> None:

        for actor_entity in actor_entities:
            self._remove_action_components(actor_entity, action_components)

    ###############################################################################################################################################
    def _remove_action_components(
        self, actor_entity: Entity, action_components: Set[type[Any]] = {GoToAction}
    ) -> None:

        for action_component in action_components:
            if actor_entity.has(action_component):
                actor_entity.remove(action_component)

    ###############################################################################################################################################
    def _has_conditions(self, stage_entity: Entity) -> bool:

        assert stage_entity.has(StageComponent)
        assert stage_entity.has(KickOffContentComponent)
        return (
            prompt_utils.PromptTag.STAGE_ENTRY_TAG
            in stage_entity.get(KickOffContentComponent).content
        )

    ###############################################################################################################################################
