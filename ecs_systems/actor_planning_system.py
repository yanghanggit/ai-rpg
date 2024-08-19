from entitas import Entity, Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from ecs_systems.components import ActorComponent, AutoPlanningComponent
from ecs_systems.action_components import (
    StageNarrateAction,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
)
from my_agent.agent_plan import AgentPlan
from my_agent.agent_action import AgentAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict
import gameplay.planning_helper
import ecs_systems.cn_builtin_prompt as builtin_prompt
from my_agent.lang_serve_agent_request_task import (
    LangServeAgentRequestTask,
    LangServeAgentAsyncRequestTasksGather,
)


class ActorPlanningSystem(ExecuteProcessor):
    """
    角色的计划系统，必须在StagePlanningSystem之后执行
    """

    def __init__(self, context: RPGEntitasContext) -> None:
        self._context = context
        self._tasks: Dict[str, LangServeAgentRequestTask] = {}

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    #######################################################################################################################################
    @override
    async def async_pre_execute(self) -> None:
        # step1: 添加任务
        self._tasks.clear()
        self.fill_tasks(self._tasks)
        # step可选：混沌工程做测试
        self._context._chaos_engineering_system.on_actor_planning_system_execute(
            self._context
        )
        # step2: 并行执行requests
        if len(self._tasks) == 0:
            return

        gather = LangServeAgentAsyncRequestTasksGather(
            "ActorPlanningSystem", self._tasks
        )
        response = await gather.gather()
        if len(response) == 0:
            logger.warning(f"ActorPlanningSystem: request_result is empty.")
            return

        self.handle(self._tasks)
        self._tasks.clear()

    #######################################################################################################################################
    def handle(self, request_tasks: Dict[str, LangServeAgentRequestTask]) -> None:

        for name, task in request_tasks.items():

            if task is None:
                logger.warning(
                    f"ActorPlanningSystem: response is None or empty, so we can't get the planning."
                )
                continue

            entity = self._context.get_actor_entity(name)
            assert entity is not None, f"ActorPlanningSystem: entity is None, {name}"
            if entity is None:
                logger.warning(f"ActorPlanningSystem: entity is None, {name}")
                continue

            actor_comp = entity.get(ActorComponent)
            actor_planning = AgentPlan(actor_comp.name, task.response_content)
            if not gameplay.planning_helper.check_plan(
                entity, actor_planning, ACTOR_AVAILABLE_ACTIONS_REGISTER
            ):
                logger.warning(
                    f"ActorPlanningSystem: check_plan failed, {actor_planning}"
                )
                ## 需要失忆!
                self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(
                    actor_comp.name
                )
                continue

            ## 不能停了，只能一直继续
            for action in actor_planning._actions:
                gameplay.planning_helper.add_action_component(
                    entity, action, ACTOR_AVAILABLE_ACTIONS_REGISTER
                )

    #######################################################################################################################################
    # 获取场景的环境描述
    def get_stage_enviro_narrate(self, entity: Entity) -> tuple[str, str]:

        stage_entity = self._context.safe_get_stage_entity(entity)
        if stage_entity is None:
            logger.error("stage is None, actor无所在场景是有问题的")
            return "", ""

        stage_name = self._context.safe_get_entity_name(stage_entity)
        stage_enviro_narrate = ""
        if stage_entity.has(StageNarrateAction):
            action: AgentAction = stage_entity.get(StageNarrateAction).action
            stage_enviro_narrate = action.join_values()

        return stage_name, stage_enviro_narrate

    #######################################################################################################################################
    def fill_tasks(
        self, out_put_request_tasks: Dict[str, LangServeAgentRequestTask]
    ) -> None:

        out_put_request_tasks.clear()

        actor_entities = self._context.get_group(
            Matcher(all_of=[ActorComponent, AutoPlanningComponent])
        ).entities
        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            agent = self._context._langserve_agent_system.get_agent(actor_comp.name)
            if agent is None:
                continue

            tp = self.get_stage_enviro_narrate(actor_entity)
            if tp[0] == "" or tp[1] == "":
                logger.error(f"{actor_comp.name} get_stage_enviro_narrate error")
                continue

            task = LangServeAgentRequestTask.create(
                agent, builtin_prompt.actor_plan_prompt(tp[0], tp[1])
            )
            if task is not None:
                out_put_request_tasks[actor_comp.name] = task

    #######################################################################################################################################
