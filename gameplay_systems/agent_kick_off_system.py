from entitas import Entity, Matcher, InitializeProcessor, ExecuteProcessor  # type: ignore
from overrides import override
from gameplay_systems.components import (
    WorldComponent,
    StageComponent,
    ActorComponent,
    AppearanceComponent,
    BodyComponent,
)
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict, Set, FrozenSet, Any
from lang_serve_agent.agent_task import (
    AgentTask,
    AgentTasksGather,
)
from rpg_game.rpg_game import RPGGame
from file_system.files_def import PropFile
from gameplay_systems.action_components import (
    STAGE_AVAILABLE_ACTIONS_REGISTER,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
)
import gameplay_systems.planning_helper
from lang_serve_agent.agent_plan_and_action import AgentPlan
from gameplay_systems.action_components import UpdateAppearanceAction


######################################################################################################################################################
class AgentKickOffSystem(InitializeProcessor, ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

        self._tasks: Dict[str, AgentTask] = {}
        self._world_tasks: Dict[str, AgentTask] = {}
        self._stage_tasks: Dict[str, AgentTask] = {}
        self._actor_tasks: Dict[str, AgentTask] = {}

    ######################################################################################################################################################
    def clear_tasks(self) -> None:
        self._tasks.clear()
        self._world_tasks.clear()
        self._stage_tasks.clear()
        self._actor_tasks.clear()

    ######################################################################################################################################################
    @override
    def initialize(self) -> None:
        # 清除
        self.clear_tasks()
        # 生成任务
        self._world_tasks = self.create_world_system_tasks()
        self._stage_tasks = self.create_stage_tasks()
        self._actor_tasks = self.create_actor_tasks()
        # self.handle_players()
        # 填进去
        self._tasks.update(self._world_tasks)
        self._tasks.update(self._stage_tasks)
        self._tasks.update(self._actor_tasks)

    ######################################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ######################################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        if len(self._tasks) == 0:
            return

        gather = AgentTasksGather("", [task for task in self._tasks.values()])
        response = await gather.gather()
        if len(response) == 0:
            return

        self.on_response(self._tasks)
        self.clear_tasks()  # 这句必须得走.
        self.on_add_update_appearance_action()

    ######################################################################################################################################################
    def create_world_system_tasks(self) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        world_entities: Set[Entity] = self._context.get_group(
            Matcher(WorldComponent)
        ).entities
        for world_entity in world_entities:

            world_comp = world_entity.get(WorldComponent)
            agent = self._context._langserve_agent_system.get_agent(world_comp.name)
            if agent is None:
                continue

            task = AgentTask.create(
                agent,
                builtin_prompt.make_kick_off_world_system_prompt(
                    self._game.about_game, self._game.round
                ),
            )
            if task is not None:
                ret[world_comp.name] = task

        return ret

    ######################################################################################################################################################
    def create_stage_tasks(self) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        stage_entities: Set[Entity] = self._context.get_group(
            Matcher(StageComponent)
        ).entities
        for stage_entity in stage_entities:

            stage_comp = stage_entity.get(StageComponent)
            agent = self._context._langserve_agent_system.get_agent(stage_comp.name)
            if agent is None:
                continue

            kick_off_messages = self._context._kick_off_message_system.get_message(
                stage_comp.name
            )
            if len(kick_off_messages) == 0 or len(kick_off_messages) > 1:
                logger.error(f"kick_off_messages is error: {stage_comp.name}")
                continue

            kick_off_prompt = builtin_prompt.make_kick_off_stage_prompt(
                kick_off_messages[0].content,
                self._game.about_game,
                self._context._file_system.get_files(
                    PropFile, self._context.safe_get_entity_name(stage_entity)
                ),
                self._context.get_actor_names_in_stage(stage_entity),
                self._game.round,
            )

            task = AgentTask.create(agent, kick_off_prompt)
            if task is not None:
                ret[stage_comp.name] = task

        return ret

    ######################################################################################################################################################
    def create_actor_tasks(self) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        actor_entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[ActorComponent])
        ).entities
        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            agent = self._context._langserve_agent_system.get_agent(actor_comp.name)
            if agent is None:
                continue

            kick_off_messages = self._context._kick_off_message_system.get_message(
                actor_comp.name
            )
            if len(kick_off_messages) == 0 or len(kick_off_messages) > 1:
                logger.error(f"kick_off_messages is error: {actor_comp.name}")
                continue

            task = AgentTask.create(
                agent,
                builtin_prompt.make_kick_off_actor_prompt(
                    kick_off_messages[0].content,
                    self._game.about_game,
                    self._game.round,
                ),
            )
            if task is not None:
                ret[actor_comp.name] = task

        return ret

    ######################################################################################################################################################
    def on_response(self, tasks: Dict[str, AgentTask]) -> None:

        for name, task in tasks.items():

            if task is None:
                logger.warning(
                    f"ActorPlanningSystem: response is None or empty, so we can't get the planning."
                )
                continue

            if name in self._world_tasks:
                continue

            agent_planning = AgentPlan(name, task.response_content)
            entity = self._context.get_actor_entity(
                name
            ) or self._context.get_stage_entity(name)
            if entity is None:
                logger.warning(f"ActorPlanningSystem: entity is None, {name}")
                continue

            if not gameplay_systems.planning_helper.check_plan(
                entity, agent_planning, self.get_actions_register(name)
            ):
                logger.warning(
                    f"ActorPlanningSystem: check_plan failed, {agent_planning}"
                )
                ## 需要失忆!
                self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(
                    name
                )
                continue

            ## 不能停了，只能一直继续
            for action in agent_planning._actions:
                gameplay_systems.planning_helper.add_action_component(
                    entity, action, self.get_actions_register(name)
                )

    ######################################################################################################################################################
    def get_actions_register(self, name: str) -> FrozenSet[type[Any]]:
        if name in self._stage_tasks:
            return STAGE_AVAILABLE_ACTIONS_REGISTER
        elif name in self._actor_tasks:
            return ACTOR_AVAILABLE_ACTIONS_REGISTER
        return frozenset()

    ######################################################################################################################################################
    def on_add_update_appearance_action(self) -> None:

        ## 第一次强制更新外观
        actor_entities = self._context.get_group(
            Matcher(all_of=[ActorComponent, AppearanceComponent, BodyComponent])
        ).entities

        for actor_entity in actor_entities:
            if not actor_entity.has(UpdateAppearanceAction):
                safe_name = self._context.safe_get_entity_name(actor_entity)
                actor_entity.add(
                    UpdateAppearanceAction,
                    safe_name,
                    UpdateAppearanceAction.__name__,
                    [],
                )

    ######################################################################################################################################################
