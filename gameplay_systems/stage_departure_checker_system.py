from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from my_components.action_components import (
    GoToAction,
    TagAction,
    DeadAction,
    WhisperAction,
)
from my_components.components import (
    ActorComponent,
    KickOffContentComponent,
    StageComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
import gameplay_systems.builtin_prompt_utils as builtin_prompt_utils
from typing import final, override, List, Set, Any, Dict
from gameplay_systems.actor_entity_utils import ActorStatusEvaluator
from my_agent.agent_task import AgentTask
from my_agent.agent_plan import AgentPlanResponse
from extended_systems.prop_file import (
    PropFile,
    generate_prop_file_for_stage_condition_prompt,
)
from rpg_game.rpg_game import RPGGame
from my_models.event_models import AgentEvent
from my_agent.lang_serve_agent import LangServeAgent


def _generate_exit_conditions_prompt(
    actor_name: str,
    current_stage_name: str,
    actor_status_prompt: str,
    prop_files: List[PropFile],
) -> str:

    prop_prompt_list = "无"
    if len(prop_files) > 0:
        prop_prompt_list = "\n".join(
            [generate_prop_file_for_stage_condition_prompt(prop) for prop in prop_files]
        )

    ret_prompt = f"""# {actor_name} 想要离开场景: {current_stage_name}。
## 第1步: 请回顾你的 {builtin_prompt_utils.ConstantPromptTag.STAGE_EXIT_TAG}

## 第2步: 根据当前‘你的状态’判断是否满足允许{actor_name}离开
当前状态可能由于事件而变化，请仔细考虑。

## 第3步: 检查{actor_name}的状态是否符合离开的需求:
### 当前角色状态: 
{actor_status_prompt if actor_status_prompt != "" else "无"}

## 第4步: 检查{actor_name}的道具(与拥有的特殊能力)是否符合以下要求:
### 当前角色道具与特殊能力信息: 
{prop_prompt_list}

# 判断结果
- 完成以上步骤后，决定是否允许 {actor_name} 离开 {current_stage_name}。

# 本次输出结果格式要求。需遵循 输出格式指南:
{{
    {WhisperAction.__name__}: ["@角色名字(你要对谁说,只能是场景内的角色)>你想私下说的内容，即描述允许离开或不允许的原因，使{actor_name}明白"],
    {TagAction.__name__}: ["Yes/No"]
}}
## 附注
- {WhisperAction.__name__} 中描述的判断理由。如果不允许离开，就只说哪一条不符合要求，不要都说出来，否则会让{actor_name}迷惑，和造成不必要的提示，影响玩家解谜的乐趣。
- Yes: 允许离开
- No: 不允许离开
"""

    return ret_prompt


################################################################################################################################################
def _generate_stage_exit_failure_prompt(
    actor_name: str, current_stage_name: str, show_tips: str
) -> str:
    return f"""# {actor_name} 想要离开场景: {current_stage_name}，但是失败了。
## 说明:
{show_tips}"""


###############################################################################################################################################
@final
class InternalPlanResponse(AgentPlanResponse):

    def __init__(self, name: str, response_content: str) -> None:
        super().__init__(name, response_content)

    @property
    def is_allowed(self) -> bool:
        return self._parse_boolean(TagAction.__name__)

    @property
    def hint(self) -> str:
        return self._concatenate_values(WhisperAction.__name__)


###############################################################################################################################################


@final
class StageDepartureCheckerSystem(ReactiveProcessor):

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
            # 直接放弃掉，全部删除
            self._remove_all_entities_actions(entities)
            return

        self._handle_agent_responses(agent_tasks)

    ######################################################################################################################################################
    def _initialize_agent_tasks(
        self, actor_entities: List[Entity]
    ) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        for actor_entity in actor_entities:

            # 必须有场景
            current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
            assert current_stage_entity is not None
            if not self._has_conditions(current_stage_entity):
                # 没有离开条件就过
                continue

            # 必须是能推理的场景
            stage_agent = self._context.agent_system.get_agent(
                self._context.safe_get_entity_name(current_stage_entity)
            )
            assert stage_agent is not None, "Stage agent is None"
            if stage_agent is None:
                continue

            # 加入返回值
            ret[self._context.safe_get_entity_name(actor_entity)] = (
                self._generate_agent_task(actor_entity, stage_agent)
            )

        return ret

    ######################################################################################################################################################
    def _generate_agent_task(
        self, actor_entity: Entity, stage_agent: LangServeAgent
    ) -> AgentTask:

        actor_status_evaluator = ActorStatusEvaluator(self._context, actor_entity)
        prompt = _generate_exit_conditions_prompt(
            actor_status_evaluator.actor_name,
            actor_status_evaluator.stage_name,
            actor_status_evaluator.appearance,
            actor_status_evaluator.available_stage_condition_prop_files,
        )

        return AgentTask.create_with_input_only_context(stage_agent, prompt)

    ######################################################################################################################################################
    def _handle_agent_responses(self, tasks: Dict[str, AgentTask]) -> None:

        for actor_name, stage_agent_task in tasks.items():

            actor_entity = self._context.get_actor_entity(actor_name)
            assert actor_entity is not None

            if stage_agent_task.response_content == "":
                # 无回应，直接删除
                self._remove_action_components(actor_entity)
                continue

            agent_response_plan = InternalPlanResponse(
                stage_agent_task.agent_name, stage_agent_task.response_content
            )

            if not agent_response_plan.is_allowed:

                # 通知失败
                self._context.notify_event(
                    set({actor_entity}),
                    AgentEvent(
                        message=_generate_stage_exit_failure_prompt(
                            actor_name,
                            stage_agent_task.agent_name,
                            agent_response_plan.hint,
                        )
                    ),
                )

                # 删除所有行动, 因为不允许离开
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
            builtin_prompt_utils.ConstantPromptTag.STAGE_EXIT_TAG
            in stage_entity.get(KickOffContentComponent).content
        )

    ###############################################################################################################################################
