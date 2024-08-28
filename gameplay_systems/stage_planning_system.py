from entitas import Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from gameplay_systems.components import StageComponent, AutoPlanningComponent
from gameplay_systems.action_components import STAGE_AVAILABLE_ACTIONS_REGISTER
from my_agent.agent_plan import AgentPlan
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict
import gameplay_systems.planning_helper
from file_system.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from my_agent.lang_serve_agent_request_task import (
    LangServeAgentRequestTask,
    LangServeAgentAsyncRequestTasksGather,
)
from rpg_game.rpg_game import RPGGame


#######################################################################################################################################
class StagePlanningSystem(ExecuteProcessor):
    """
    场景计划系统
    """

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._tasks: Dict[str, LangServeAgentRequestTask] = {}

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    #######################################################################################################################################
    @override
    async def pre_execute(self) -> None:
        # step1: 添加任务
        self._tasks.clear()
        self.fill_tasks(self._tasks)
        # step可选：混沌工程做测试
        self._context._chaos_engineering_system.on_stage_planning_system_excute(
            self._context
        )
        # step2: 并行执行requests
        if len(self._tasks) == 0:
            return

        gather = LangServeAgentAsyncRequestTasksGather("", self._tasks)
        response = await gather.gather()
        if len(response) == 0:
            logger.warning(f"StagePlanningSystem: request_result is empty.")
            return

        # step3: 处理结果
        self.handle(self._tasks)
        self._tasks.clear()

    #######################################################################################################################################
    def handle(self, request_tasks: Dict[str, LangServeAgentRequestTask]) -> None:

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

            stage_planning = AgentPlan(name, task.response_content)
            if not gameplay_systems.planning_helper.check_plan(
                stage_entity, stage_planning, STAGE_AVAILABLE_ACTIONS_REGISTER
            ):
                logger.warning(
                    f"StagePlanningSystem: check_plan failed, {stage_planning}"
                )
                ## 需要失忆!
                self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(
                    name
                )
                continue

            ## 不能停了，只能一直继续
            for action in stage_planning._actions:
                gameplay_systems.planning_helper.add_action_component(
                    stage_entity, action, STAGE_AVAILABLE_ACTIONS_REGISTER
                )

    #######################################################################################################################################
    def fill_tasks(
        self, out_put_request_tasks: Dict[str, LangServeAgentRequestTask]
    ) -> None:
        out_put_request_tasks.clear()

        stage_entities = self._context.get_group(
            Matcher(all_of=[StageComponent, AutoPlanningComponent])
        ).entities
        for stage_entity in stage_entities:

            stage_comp = stage_entity.get(StageComponent)
            agent = self._context._langserve_agent_system.get_agent(stage_comp.name)
            if agent is None:
                continue

            task = LangServeAgentRequestTask.create(
                agent,
                builtin_prompt.make_stage_plan_prompt(
                    self._context._file_system.get_files(
                        PropFile,
                        self._context.safe_get_entity_name(stage_entity),
                    ),
                    self._game.round,
                    self._context.get_appearance_in_stage(stage_entity),
                ),
            )

            if task is not None:
                out_put_request_tasks[stage_comp.name] = task


#######################################################################################################################################
