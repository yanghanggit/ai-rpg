from entitas import Entity, Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from my_components.components import (
    ActorComponent,
    PlanningAllowedComponent,
    StageGraphComponent,
    PlayerComponent,
    AgentConnectionFlagComponent,
    KickOffFlagComponent,
)
from my_components.action_components import (
    StageNarrateAction,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
    GoToAction,
    TagAction,
)
from my_agent.agent_plan import AgentPlanResponse
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict, Set, List, Optional, final
import gameplay_systems.action_utils
import gameplay_systems.prompt_utils as prompt_utils
from my_agent.agent_task import (
    AgentTask,
)
from rpg_game.rpg_game import RPGGame
from gameplay_systems.actor_entity_utils import ActorStatusEvaluator
from extended_systems.prop_file import (
    PropFile,
    generate_prop_file_total_prompt,
)
from my_models.file_models import PropType


###############################################################################################################################################
def _generate_props_prompt(
    prop_info: Dict[str, List[PropFile]],
    order_keys: List[str] = [
        PropType.TYPE_SPECIAL,
        PropType.TYPE_WEAPON,
        PropType.TYPE_CLOTHES,
        PropType.TYPE_NON_CONSUMABLE_ITEM,
        PropType.TYPE_SKILL,
    ],
) -> List[str]:

    ret: List[str] = []

    for key in order_keys:
        if key not in prop_info:
            continue

        for prop_file in prop_info[key]:
            ret.append(generate_prop_file_total_prompt(prop_file))

    return ret


###############################################################################################################################################
def _generate_actor_plan_prompt(
    current_stage: str,
    stage_enviro_narrate: str,
    stage_graph: Set[str],
    actor_appearance_mapping: Dict[str, str],
    health: float,
    actor_props: Dict[str, List[PropFile]],
    current_weapon: Optional[PropFile],
    current_clothes: Optional[PropFile],
) -> str:

    assert current_stage != "", "current_stage is empty"

    # 组织生成角色道具描述
    health *= 100

    # 组织生成角色道具描述
    props_prompt = _generate_props_prompt(actor_props)
    if len(props_prompt) == 0:
        props_prompt.append("无任何道具。")

    # 组织生成角色外观描述
    actor_appearance_mapping_prompt: List[str] = []
    for actor_name, actor_appearance in actor_appearance_mapping.items():
        actor_appearance_mapping_prompt += f"""### {actor_name}
角色外观:{actor_appearance}"""

    if len(actor_appearance_mapping_prompt) == 0:
        actor_appearance_mapping_prompt.append("无任何角色。")

    #
    if len(stage_graph) == 0:
        stage_graph.add(f"无可去往场景(你不可以执行{GoToAction.__name__})")

    return f"""# 请制定你的计划
- 标记 {prompt_utils.PromptTag.ACTOR_PLAN_PROMPT_TAG} 
- 规则见‘游戏流程’-制定计划

## 你当前所在的场景
{current_stage}
### 场景描述
{stage_enviro_narrate}
### 从本场景可以去往的场景
{"\n".join(stage_graph)}   

## 场景内的角色
{"\n".join(actor_appearance_mapping_prompt)}

## 你的健康状态
{f"生命值: {health:.2f}%"}

## 你的道具
{"\n".join(props_prompt)}

## 你当前装备的道具
- {current_weapon is not None and current_weapon.name or "无"}
- {current_clothes is not None and current_clothes.name or "无"}

## 小建议
- 请随时保持装备武器与衣服的状态(前提是你拥有）。

## 输出要求
- 请遵循 输出格式指南。
- 返回结果 至少 包含 {TagAction.__name__}。"""


#######################################################################################################################################


@final
class ActorPlanningExecutionSystem(ExecuteProcessor):

    @override
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    #######################################################################################################################################
    @override
    async def a_execute1(self) -> None:
        # step1: 添加任务
        tasks: Dict[str, AgentTask] = {}
        self._populate_agent_tasks(tasks)
        # step可选：混沌工程做测试
        self._context._chaos_engineering_system.on_actor_planning_system_execute(
            self._context
        )
        # step2: 并行执行requests
        if len(tasks) == 0:
            return

        responses = await AgentTask.gather([task for task in tasks.values()])
        if len(responses) == 0:
            logger.warning(f"ActorPlanningSystem: request_result is empty.")
            return

        self._process_agent_tasks(tasks)
        tasks.clear()

    #######################################################################################################################################
    def _process_agent_tasks(self, request_tasks: Dict[str, AgentTask]) -> None:

        for actor_name, agent_task in request_tasks.items():

            entity = self._context.get_actor_entity(actor_name)
            assert (
                entity is not None
            ), f"ActorPlanningSystem: entity is None, {actor_name}"

            actor_planning = AgentPlanResponse(actor_name, agent_task.response_content)
            if not gameplay_systems.action_utils.validate_actions(
                actor_planning, ACTOR_AVAILABLE_ACTIONS_REGISTER
            ):
                logger.warning(
                    f"ActorPlanningSystem: check_plan failed, {actor_planning.original_response_content}"
                )
                ## 需要失忆!
                self._context.agent_system.remove_last_human_ai_conversation(actor_name)
                continue

            ## 不能停了，只能一直继续
            for action in actor_planning._actions:
                gameplay_systems.action_utils.add_action(
                    entity, action, ACTOR_AVAILABLE_ACTIONS_REGISTER
                )

    #######################################################################################################################################
    def _populate_agent_tasks(self, planned_agent_tasks: Dict[str, AgentTask]) -> None:

        planned_agent_tasks.clear()

        actor_entities = self._context.get_group(
            Matcher(
                all_of=[
                    ActorComponent,
                    PlanningAllowedComponent,
                    AgentConnectionFlagComponent,
                    KickOffFlagComponent,
                ],
                none_of=[PlayerComponent],
            )
        ).entities
        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            agent = self._context.agent_system.get_agent(actor_comp.name)
            if agent is None:
                continue

            check_self = ActorStatusEvaluator(self._context, actor_entity)
            actors_appearance = self._context.gather_actor_appearance_in_stage(
                actor_entity
            )
            actors_appearance.pop(actor_comp.name, None)  # 自己不要

            planned_agent_tasks[actor_comp.name] = AgentTask.create_with_full_context(
                agent,
                _generate_actor_plan_prompt(
                    current_stage=self._retrieve_stage_name(actor_entity),
                    stage_enviro_narrate=self._retrieve_stage_narrative(actor_entity),
                    stage_graph=set(self._retrieve_stage_graph(actor_entity)),
                    actor_appearance_mapping=actors_appearance,
                    health=check_self.health,
                    actor_props=check_self._category_prop_files,
                    current_weapon=check_self._current_weapon,
                    current_clothes=check_self._current_clothes,
                ),
            )

    #######################################################################################################################################
    def _retrieve_stage_name(self, actor_entity: Entity) -> str:
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        assert stage_entity is not None, "stage is None, actor无所在场景是有问题的"
        return self._context.safe_get_entity_name(stage_entity)

    #######################################################################################################################################
    def _retrieve_stage_narrative(self, actor_entity: Entity) -> str:
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        assert stage_entity is not None, "stage is None, actor无所在场景是有问题的"

        if not stage_entity.has(StageNarrateAction):
            logger.warning("stage has no StageNarrateAction")
            return ""

        stage_narrate_action = stage_entity.get(StageNarrateAction)
        return " ".join(stage_narrate_action.values)

    #######################################################################################################################################
    # def _retrieve_props_in_stage(self, actor_entity: Entity) -> List[PropFile]:
    #     stage_entity = self._context.safe_get_stage_entity(actor_entity)
    #     assert stage_entity is not None, "stage is None, actor无所在场景是有问题的"
    #     return self._context._file_system.get_files(
    #         PropFile, self._context.safe_get_entity_name(stage_entity)
    #     )

    #######################################################################################################################################
    def _retrieve_stage_graph(self, actor_entity: Entity) -> List[str]:
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        assert stage_entity is not None, "stage is None, actor无所在场景是有问题的"
        return stage_entity.get(StageGraphComponent).stage_graph.copy()

    #######################################################################################################################################
