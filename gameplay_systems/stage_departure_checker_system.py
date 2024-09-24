from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from gameplay_systems.action_components import (
    GoToAction,
    TagAction,
    DeadAction,
    WhisperAction,
)
from gameplay_systems.components import ActorComponent, AppearanceComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from gameplay_systems.cn_constant_prompt import CNConstantPrompt as ConstantPrompt
from typing import cast, override, List, Set, Any, Dict, Optional
from gameplay_systems.check_self_helper import CheckSelfHelper
from my_agent.agent_task import AgentTask, AgentTasksGather
from my_agent.agent_plan_and_action import AgentPlan
from extended_systems.files_def import PropFile
from rpg_game.rpg_game import RPGGame
from my_data.model_def import PropType


class StageDepartureCheckResponse(AgentPlan):

    def __init__(self, name: str, input_str: str) -> None:
        super().__init__(name, input_str)

    @property
    def allow(self) -> bool:
        tip_action = self.get_by_key(TagAction.__name__)
        if tip_action is None or len(tip_action.values) == 0:
            return False
        first_value = tip_action.values[0].lower()
        return first_value == "yes" or first_value == "true"

    @property
    def tips(self) -> str:
        whisper_action = self.get_by_key(WhisperAction.__name__)
        if whisper_action is None or len(whisper_action.values) == 0:
            return ""
        return whisper_action.values[0]


###############################################################################################################################################


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

        tasks = self.create_tasks(entities)
        if len(tasks) == 0:
            return

        responses = await AgentTasksGather(
            "",
            [task for task in tasks.values()],
        ).gather()

        if len(responses) == 0:
            self.on_remove_all(entities)
            return

        self.handle_tasks(tasks)

    ######################################################################################################################################################
    def create_tasks(self, actor_entities: List[Entity]) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        for actor_entity in actor_entities:

            current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
            assert current_stage_entity is not None
            if not self.has_conditions(current_stage_entity):
                continue

            task = self.create_task(actor_entity)
            if task is not None:
                ret[self._context.safe_get_entity_name(actor_entity)] = task
            else:
                self.on_remove_action(actor_entity)

        return ret

    ######################################################################################################################################################
    def create_task(self, actor_entity: Entity) -> Optional[AgentTask]:
        #
        current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
        assert current_stage_entity is not None

        current_stage_name = self._context.safe_get_entity_name(current_stage_entity)
        stage_agent = self._context._langserve_agent_system.get_agent(
            current_stage_name
        )
        if stage_agent is None:
            return None

        actor_name = self._context.safe_get_entity_name(actor_entity)
        prompt = builtin_prompt.stage_exit_conditions_check_prompt(
            actor_name,
            current_stage_name,
            self.get_actor_appearance_prompt(actor_entity),
            self.get_actor_props(actor_entity),
        )

        return AgentTask.create(stage_agent, prompt)

    ######################################################################################################################################################
    def handle_tasks(self, tasks: Dict[str, AgentTask]) -> None:

        for actor_name, stage_agent_task in tasks.items():
            if stage_agent_task.response_content == "":
                continue

            response_plan = StageDepartureCheckResponse(
                stage_agent_task.agent_name, stage_agent_task.response_content
            )

            if not response_plan.allow:

                actor_entity = self._context.get_actor_entity(actor_name)
                assert actor_entity is not None

                self._context.broadcast_entities(
                    set({actor_entity}),
                    builtin_prompt.exit_stage_failed_beacuse_stage_refuse_prompt(
                        actor_name, stage_agent_task.agent_name, response_plan.tips
                    ),
                )

                self.on_remove_action(actor_entity)

            else:

                self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(
                    stage_agent_task.agent_name
                )

    ###############################################################################################################################################
    def on_remove_all(
        self, entities: List[Entity], action_comps: Set[type[Any]] = {GoToAction}
    ) -> None:

        for entity in entities:
            self.on_remove_action(entity, action_comps)

    ###############################################################################################################################################
    def on_remove_action(
        self, entity: Entity, action_comps: Set[type[Any]] = {GoToAction}
    ) -> None:

        for action_comp in action_comps:
            if entity.has(action_comp):
                entity.remove(action_comp)

    ###############################################################################################################################################
    def has_conditions(self, stage_entity: Entity) -> bool:
        safe_name = self._context.safe_get_entity_name(stage_entity)
        kickoff = self._context._kick_off_message_system.get_message(safe_name)
        if len(kickoff) == 0:
            return False
        return ConstantPrompt.STAGE_EXIT_TAG in kickoff[0].content

    ###############################################################################################################################################
    def get_actor_appearance_prompt(self, actor_entity: Entity) -> str:
        assert actor_entity.has(ActorComponent)
        if not actor_entity.has(AppearanceComponent):
            return ""
        appearance_comp = actor_entity.get(AppearanceComponent)
        return cast(str, appearance_comp.appearance)

    ###############################################################################################################################################
    def get_actor_props(self, actor_entity: Entity) -> List[PropFile]:

        check_self = CheckSelfHelper(self._context, actor_entity)
        return (
            check_self.get_prop_files(PropType.TYPE_SPECIAL)
            + check_self.get_prop_files(PropType.TYPE_WEAPON)
            + check_self.get_prop_files(PropType.TYPE_CLOTHES)
            + check_self.get_prop_files(PropType.TYPE_NON_CONSUMABLE_ITEM)
        )

    ###############################################################################################################################################
