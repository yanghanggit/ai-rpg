from entitas import Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from my_components.components import (
    StageComponent,
    PlanningAllowedComponent,
    AgentConnectionFlagComponent,
    KickOffFlagComponent,
)
from my_components.action_components import (
    StageNarrateAction,
    StageTagAction,
    TagAction,
)
from my_agent.agent_plan import AgentPlanResponse
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict, List, final
import gameplay_systems.action_component_utils
import gameplay_systems.prompt_utils
from my_agent.agent_task import (
    AgentTask,
)
from rpg_game.rpg_game import RPGGame


###############################################################################################################################################
def _generate_stage_plan_prompt(
    actor_appearance_mapping: Dict[str, str],
) -> str:

    # 组织生成角色外观描述
    actor_appearance_mapping_prompt: List[str] = []
    for actor_name, actor_appearance in actor_appearance_mapping.items():
        actor_appearance_mapping_prompt.append(
            f"""### {actor_name}
角色外观:{actor_appearance}"""
        )

    if len(actor_appearance_mapping_prompt) == 0:
        actor_appearance_mapping_prompt.append("无任何角色。")

    # 最终生成
    return f"""# 请制定你的计划({gameplay_systems.prompt_utils.PromptTag.STAGE_PLAN_PROMPT_TAG})
规则见 游戏流程 - 制定计划

## 场景内的角色
{"\n".join(actor_appearance_mapping_prompt)}

{gameplay_systems.prompt_utils.generate_stage_narrate_action_prompt()}

## 输出要求
- 请遵循 输出格式指南。
- 返回结果 至少 包含 {StageNarrateAction.__name__} 和 {TagAction.__name__}。"""


#######################################################################################################################################
@final
class StagePlanningExecutionSystem(ExecuteProcessor):

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
        self._context.chaos_engineering_system.on_stage_planning_system_excute(
            self._context
        )

        # step2: 并行执行requests
        if len(tasks) == 0:
            return

        responses = await AgentTask.gather([task for task in tasks.values()])
        if len(responses) == 0:
            logger.warning(f"StagePlanningSystem: request_result is empty.")
            return

        # step3: 处理结果
        self._process_agent_tasks(tasks)

        # step4: 保底加一个行为？
        self._ensure_stage_actions(tasks)

        # step？: 清理，习惯性动作
        tasks.clear()

    #######################################################################################################################################
    def _process_agent_tasks(self, agent_task_requests: Dict[str, AgentTask]) -> None:

        for stage_name, agent_task in agent_task_requests.items():

            stage_entity = self._context.get_stage_entity(stage_name)
            assert (
                stage_entity is not None
            ), f"StagePlanningSystem: stage_entity is None, {stage_name}"
            if stage_entity is None:
                continue

            action_add_result = (
                gameplay_systems.action_component_utils.add_stage_actions(
                    self._context,
                    stage_entity,
                    AgentPlanResponse(stage_name, agent_task.response_content),
                )
            )

            if not action_add_result:
                logger.warning("StagePlanningSystem: action_add_result is False.")
                self._context.discard_last_human_ai_conversation(stage_entity)
                continue

    #######################################################################################################################################
    def _populate_agent_tasks(
        self, requested_agent_tasks: Dict[str, AgentTask]
    ) -> None:
        requested_agent_tasks.clear()

        stage_entities = self._context.get_group(
            Matcher(
                all_of=[
                    StageComponent,
                    PlanningAllowedComponent,
                    AgentConnectionFlagComponent,
                    KickOffFlagComponent,
                ]
            )
        ).entities
        for stage_entity in stage_entities:
            agent = self._context.safe_get_agent(stage_entity)
            requested_agent_tasks[agent.name] = AgentTask.create_with_full_context(
                agent,
                _generate_stage_plan_prompt(
                    self._context.retrieve_stage_actor_appearance(stage_entity),
                ),
            )

    #######################################################################################################################################
    def _ensure_stage_actions(self, agent_task_requests: Dict[str, AgentTask]) -> None:
        for stage_name, agent_task in agent_task_requests.items():

            stage_entity = self._context.get_stage_entity(stage_name)
            assert (
                stage_entity is not None
            ), f"StagePlanningSystem: stage_entity is None, {stage_name}"
            if stage_entity is None:
                continue

            if not stage_entity.has(StageNarrateAction):
                logger.warning(
                    f"StagePlanningSystem: add StageNarrateAction = {stage_name}"
                )
                stage_entity.add(
                    StageNarrateAction, StageNarrateAction.__name__, ["无任何描述。"]
                )

            if not stage_entity.has(StageTagAction):
                # logger.warning(
                #     f"StagePlanningSystem: add StageTagAction = {stage_name}"
                # )
                stage_entity.add(StageTagAction, StageTagAction.__name__, [])


#######################################################################################################################################
