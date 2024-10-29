from entitas import Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from my_components.components import StageComponent, PlanningAllowedComponent
from my_components.action_components import (
    STAGE_AVAILABLE_ACTIONS_REGISTER,
    RemovePropAction,
    StageNarrateAction,
    TagAction,
)
from my_agent.agent_plan import AgentPlanResponse
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict, List, final
import gameplay_systems.action_helper
from extended_systems.files_def import PropFile
import gameplay_systems.public_builtin_prompt as public_builtin_prompt
from my_agent.agent_task import (
    AgentTask,
)
from rpg_game.rpg_game import RPGGame


###############################################################################################################################################
def _generate_stage_plan_prompt(
    props_in_stage: List[PropFile],
    game_round: int,
    info_of_actors_in_stage: Dict[str, str],
) -> str:

    props_in_stage_prompt = "- 无任何道具。"
    if len(props_in_stage) > 0:
        props_in_stage_prompt = ""
        for prop in props_in_stage:
            props_in_stage_prompt += public_builtin_prompt.generate_prop_prompt(
                prop, description_prompt=False, appearance_prompt=True
            )

    ## 场景角色
    actors_in_stage_prompt = "- 无任何角色。"
    if len(info_of_actors_in_stage) > 0:
        actors_in_stage_prompt = ""
        for actor_name, actor_appearance in info_of_actors_in_stage.items():
            actors_in_stage_prompt += (
                f"### {actor_name}\n- 角色外观:{actor_appearance}\n"
            )

    ret_prompt = f"""# {public_builtin_prompt.ConstantPrompt.STAGE_PLAN_PROMPT_TAG} 请做出你的计划，决定你将要做什么与更新你的场景描述

## 场景内的道具
{props_in_stage_prompt}

## 场景内的角色
{actors_in_stage_prompt}

## 你的计划生成规则
- 结合以上信息，决定你的下一步行动。
- 如果 场景内的道具 产生损毁与破坏等事件 (请回顾你的历史消息)，则使用 {RemovePropAction.__name__} 将其移除，以此来保证你的逻辑的连贯与合理性。

## {StageNarrateAction.__name__} 场景描述生成规则
- 不要对场景内角色未发生的对话，行为或心理活动进行任何猜测与推理。
- 注意！在输出内容中，移除所有与 场景内的角色 相关的描述。

## 输出要求
- 请遵循 输出格式指南。
- 返回结果至少包含 {StageNarrateAction.__name__} 和 {TagAction.__name__}。"""

    return ret_prompt


#######################################################################################################################################
@final
class StagePlanningExecutionSystem(ExecuteProcessor):

    @override
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._tasks: Dict[str, AgentTask] = {}

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    #######################################################################################################################################
    @override
    async def a_execute1(self) -> None:
        # step1: 添加任务
        self._tasks.clear()
        self._fill_tasks(self._tasks)
        # step可选：混沌工程做测试
        self._context._chaos_engineering_system.on_stage_planning_system_excute(
            self._context
        )
        # step2: 并行执行requests
        if len(self._tasks) == 0:
            return

        responses = await AgentTask.gather([task for task in self._tasks.values()])
        if len(responses) == 0:
            logger.warning(f"StagePlanningSystem: request_result is empty.")
            return

        # step3: 处理结果
        self._handle_tasks(self._tasks)
        self._tasks.clear()

    #######################################################################################################################################
    def _handle_tasks(self, request_tasks: Dict[str, AgentTask]) -> None:

        for name, task in request_tasks.items():

            if task is None:
                logger.warning(
                    f"StagePlanningSystem: response is None or empty, so we can't get the planning."
                )
                continue

            stage_entity = self._context.get_stage_entity(name)
            assert (
                stage_entity is not None
            ), f"StagePlanningSystem: stage_entity is None, {name}"
            if stage_entity is None:
                logger.warning(f"StagePlanningSystem: stage_entity is None, {name}")
                continue

            stage_planning = AgentPlanResponse(name, task.response_content)
            if not gameplay_systems.action_helper.validate_actions(
                stage_planning, STAGE_AVAILABLE_ACTIONS_REGISTER
            ):
                logger.warning(
                    f"StagePlanningSystem: check_plan failed, {stage_planning}"
                )
                ## 需要失忆!
                self._context._langserve_agent_system.remove_last_human_ai_conversation(
                    name
                )
                continue

            ## 不能停了，只能一直继续
            for action in stage_planning._actions:
                gameplay_systems.action_helper.add_action(
                    stage_entity, action, STAGE_AVAILABLE_ACTIONS_REGISTER
                )

    #######################################################################################################################################
    def _fill_tasks(self, out_put_request_tasks: Dict[str, AgentTask]) -> None:
        out_put_request_tasks.clear()

        stage_entities = self._context.get_group(
            Matcher(all_of=[StageComponent, PlanningAllowedComponent])
        ).entities
        for stage_entity in stage_entities:

            stage_comp = stage_entity.get(StageComponent)
            agent = self._context._langserve_agent_system.get_agent(stage_comp.name)
            if agent is None:
                continue

            out_put_request_tasks[stage_comp.name] = AgentTask.create(
                agent,
                _generate_stage_plan_prompt(
                    self._context._file_system.get_files(
                        PropFile,
                        self._context.safe_get_entity_name(stage_entity),
                    ),
                    self._game._runtime_game_round,
                    self._context.get_appearance_in_stage(stage_entity),
                ),
            )


#######################################################################################################################################
