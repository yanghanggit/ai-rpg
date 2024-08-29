from entitas import Entity, Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from gameplay_systems.components import (
    ActorComponent,
    AutoPlanningComponent,
    StageGraphComponent,
)
from gameplay_systems.action_components import (
    StageNarrateAction,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
)
from my_agent.agent_plan import AgentPlan
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict, Set, List
import gameplay_systems.planning_helper
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from my_agent.lang_serve_agent_request_task import (
    LangServeAgentRequestTask,
    LangServeAgentAsyncRequestTasksGather,
)
from rpg_game.rpg_game import RPGGame
from gameplay_systems.check_self_helper import CheckSelfHelper
from file_system.files_def import PropFile


class ActorPlanningSystem(ExecuteProcessor):

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
        self._context._chaos_engineering_system.on_actor_planning_system_execute(
            self._context
        )
        # step2: 并行执行requests
        if len(self._tasks) == 0:
            return

        gather = LangServeAgentAsyncRequestTasksGather("", self._tasks)
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
            if not gameplay_systems.planning_helper.check_plan(
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
                gameplay_systems.planning_helper.add_action_component(
                    entity, action, ACTOR_AVAILABLE_ACTIONS_REGISTER
                )

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

            check_self = CheckSelfHelper(self._context, actor_entity)
            actors_appearance = self._context.get_appearance_in_stage(actor_entity)
            actors_appearance.pop(actor_comp.name, None)  # 自己不要

            task = LangServeAgentRequestTask.create(
                agent,
                builtin_prompt.make_actor_plan_prompt(
                    game_round=self._game.round,
                    current_stage=self.get_stage_name(actor_entity),
                    stage_enviro_narrate=self.get_stage_narrate(actor_entity),
                    stage_graph=self.get_stage_graph(actor_entity),
                    stage_props=self.get_stage_props(actor_entity),
                    stage_actors_info=actors_appearance,
                    health=check_self.health,
                    categorized_prop_files=check_self._categorized_prop_files,
                    current_weapon=check_self._current_weapon,
                    current_clothes=check_self._current_clothes,
                ),
            )
            if task is not None:
                out_put_request_tasks[actor_comp.name] = task

    #######################################################################################################################################
    def get_stage_name(self, actor_entity: Entity) -> str:
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        if stage_entity is None:
            logger.error("stage is None, actor无所在场景是有问题的")
            return ""

        return self._context.safe_get_entity_name(stage_entity)

    #######################################################################################################################################
    def get_stage_narrate(self, actor_entity: Entity) -> str:
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        if stage_entity is None:
            logger.error("stage is None, actor无所在场景是有问题的")
            return ""

        if not stage_entity.has(StageNarrateAction):
            return ""

        stage_narrate_action = stage_entity.get(StageNarrateAction)
        return " ".join(stage_narrate_action.values)

    #######################################################################################################################################
    def get_stage_props(self, actor_entity: Entity) -> List[PropFile]:
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        if stage_entity is None:
            logger.error("stage is None, actor无所在场景是有问题的")
            return []
        return self._context._file_system.get_files(
            PropFile, self._context.safe_get_entity_name(stage_entity)
        )

    #######################################################################################################################################
    def get_stage_graph(self, actor_entity: Entity) -> Set[str]:
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        if stage_entity is None:
            logger.error("stage is None, actor无所在场景是有问题的")
            return set()

        if not stage_entity.has(StageGraphComponent):
            return set()

        stage_graph: Set[str] = stage_entity.get(StageGraphComponent).stage_graph
        return stage_graph.copy()

    #######################################################################################################################################
